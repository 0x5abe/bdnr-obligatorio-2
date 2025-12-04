import json
import uuid
from datetime import datetime, timedelta

from redis.cluster import RedisCluster, ClusterNode


# Connection


def connect_cluster(nodes):
    cluster_nodes = [ClusterNode(node["host"], node["port"]) for node in nodes]

    return RedisCluster(
        startup_nodes=cluster_nodes,
        decode_responses=True,
    )


# Key Builders


def key_role(role_id: str) -> str:
    return f"sec:role:{role_id}"


def key_user_roles(user_id: str) -> str:
    return f"sec:userRoles:{user_id}"


def key_token(jti: str) -> str:
    return f"sec:token:{jti}"


def key_revoked(jti: str) -> str:
    return f"sec:revoked:{jti}"


def key_privacy_prefs(user_id: str) -> str:
    return f"privacy:prefs:{user_id}"


def key_privacy_consent(user_id: str) -> str:
    return f"privacy:consent:{user_id}"


def key_audit_events() -> str:
    return "audit:events"


def key_audit_by_user(user_id: str) -> str:
    return f"audit:byUser:{user_id}"


def key_delete_queue() -> str:
    return "privacy:deleteQueue"


def key_active_users(date_str: str) -> str:
    return f"metrics:activeUsers:{date_str}"


# Audit Stream


def add_audit_event(r, user_id: str, action: str, result: str, metadata=None):
    event = {
        "user_id": user_id,
        "action": action,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": json.dumps(metadata or {}),
    }

    r.xadd(key_audit_events(), event)
    r.xadd(key_audit_by_user(user_id), event)


def get_last_audit_events(r, count: int = 10):
    return r.xrevrange(key_audit_events(), max="+", min="-", count=count)


def get_last_audit_events_by_user(r, user_id: str, count: int = 10):
    return r.xrevrange(key_audit_by_user(user_id), max="+", min="-", count=count)


# Roles and Permissions


def add_permission_to_role(r, role_id: str, permission: str):
    r.sadd(key_role(role_id), permission)
    add_audit_event(
        r,
        "system",
        "role_permission_added",
        "success",
        {"role": role_id, "permission": permission},
    )


def remove_permission_from_role(r, role_id: str, permission: str):
    r.srem(key_role(role_id), permission)
    add_audit_event(
        r,
        "system",
        "role_permission_removed",
        "success",
        {"role": role_id, "permission": permission},
    )


def assign_role_to_user(r, user_id: str, role_id: str):
    r.sadd(key_user_roles(user_id), role_id)
    add_audit_event(r, user_id, "role_assigned", "success", {"role": role_id})


def remove_role_from_user(r, user_id: str, role_id: str):
    r.srem(key_user_roles(user_id), role_id)
    add_audit_event(r, user_id, "role_removed", "success", {"role": role_id})


def get_role_permissions(r, role_id: str):
    return r.smembers(key_role(role_id))


def get_user_roles(r, user_id: str):
    return r.smembers(key_user_roles(user_id))


def user_has_permission(r, user_id: str, permission: str) -> bool:
    roles = r.smembers(key_user_roles(user_id))
    if not roles:
        return False

    for role in roles:
        if r.sismember(key_role(role), permission):
            return True

    return False


# HyperLogLog – active users


def mark_user_active(r, user_id: str, date: datetime | None = None):
    if date is None:
        date = datetime.utcnow()
    date_str = date.strftime("%Y-%m-%d")
    key = key_active_users(date_str)
    r.pfadd(key, user_id)
    r.expire(key, 60 * 60 * 24 * 90)


def get_active_user_count(r, date: datetime | None = None) -> int:
    if date is None:
        date = datetime.utcnow()
    date_str = date.strftime("%Y-%m-%d")
    key = key_active_users(date_str)
    return r.pfcount(key)


# Tokens with TTL


def issue_token(r, user_id: str, ttl_seconds: int = 3600, scope=None) -> str:
    jti = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl_seconds)

    data = {
        "user_id": user_id,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "scope": scope or [],
    }

    r.set(key_token(jti), json.dumps(data), ex=ttl_seconds)

    add_audit_event(
        r,
        user_id,
        "token_issued",
        "success",
        {"jti": jti, "ttl_seconds": ttl_seconds},
    )

    mark_user_active(r, user_id, now)

    return jti


def revoke_token(r, jti: str, reason: str = "manual_revoke"):
    token_key = key_token(jti)
    data = r.get(token_key)

    if data:
        payload = json.loads(data)
        user_id = payload["user_id"]
        ttl = r.ttl(token_key)
    else:
        user_id = "unknown"
        ttl = 3600

    r.set(key_revoked(jti), reason, ex=max(ttl, 1))

    add_audit_event(
        r,
        user_id,
        "token_revoked",
        "success",
        {"jti": jti, "reason": reason},
    )


def validate_token(r, jti: str) -> dict | None:
    data = r.get(key_token(jti))
    if not data or r.exists(key_revoked(jti)):
        add_audit_event(
            r,
            "unknown",
            "token_validation",
            "failure",
            {"jti": jti, "reason": "not_found_or_revoked"},
        )
        return None

    payload = json.loads(data)
    expires_at = datetime.fromisoformat(payload["expires_at"])

    if datetime.utcnow() > expires_at:
        add_audit_event(
            r,
            payload["user_id"],
            "token_validation",
            "failure",
            {"jti": jti, "reason": "expired"},
        )
        return None

    add_audit_event(
        r,
        payload["user_id"],
        "token_validation",
        "success",
        {"jti": jti},
    )

    mark_user_active(r, payload["user_id"])

    return payload


# Privacy Preferences


def set_privacy_prefs(r, user_id: str, prefs: dict):
    r.set(key_privacy_prefs(user_id), json.dumps(prefs))
    add_audit_event(
        r,
        user_id,
        "privacy_prefs_updated",
        "success",
        {"prefs": prefs},
    )


def get_privacy_prefs(r, user_id: str) -> dict | None:
    data = r.get(key_privacy_prefs(user_id))
    return json.loads(data) if data else None


def add_consent_entry(r, user_id: str, consent_type: str, granted: bool):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": consent_type,
        "granted": granted,
    }

    r.rpush(key_privacy_consent(user_id), json.dumps(entry))

    add_audit_event(
        r,
        user_id,
        "privacy_consent_update",
        "success",
        entry,
    )


# Anonymization Queue


def enqueue_delete_request(r, user_id: str, reason: str):
    event = {
        "user_id": user_id,
        "reason": reason,
        "requested_at": datetime.utcnow().isoformat(),
    }

    r.xadd(key_delete_queue(), event)

    add_audit_event(
        r,
        user_id,
        "delete_request_enqueued",
        "success",
        event,
    )


def process_delete_requests(r, count: int = 10):
    results = r.xrange(key_delete_queue(), min="-", max="+", count=count)

    for entry_id, fields in results:
        user_id = fields["user_id"]

        r.delete(key_privacy_prefs(user_id))
        r.delete(key_privacy_consent(user_id))
        r.delete(key_user_roles(user_id))

        add_audit_event(
            r,
            user_id,
            "delete_request_processed",
            "success",
            {"entry_id": entry_id, "reason": fields["reason"]},
        )

    return results
