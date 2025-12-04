from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from datetime import datetime, timedelta, timezone


# Connection


def get_client(url="mongodb://localhost:27020"):
    """Return a MongoDB client connected to mongos."""
    return MongoClient(url)


def get_users_collection(client, db_name="duolingo_users", col_name="usuarios"):
    """Return the users collection."""
    return client[db_name][col_name]


# Index Creation


def ensure_indexes(col):
    """Create indexes based on documented access patterns."""
    col.create_index([("username", ASCENDING)], unique=True)
    col.create_index([("email", ASCENDING)], unique=True)
    col.create_index([("ajustes.privacidad_perfil", ASCENDING)])
    col.create_index([("ajustes.notificaciones.email", ASCENDING)])


# User Creation


def create_user(
    col,
    username,
    email,
    password_hash,
    avatar=None,
    bio=None,
    cursos=None,
    privacidad=None,
    suscripcion=None,
    amigos=None,
):
    """Create a user document with flexible structure."""

    new_user = {
        "_id": username,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "fecha_registro": datetime.now(timezone.utc),
        "2fa_enabled": False,
        "avatar": avatar,
        "bio": bio,
        "racha_actual": 0,
        "total_xp": 0,
        "nivel_actual": 1,
        "cursos": cursos if cursos else [],
        "ajustes": (
            privacidad
            if privacidad
            else {
                "privacidad_perfil": "publico",
                "permitir_amigos": True,
                "notificaciones": {"email": True, "push": True},
            }
        ),
        "suscripcion": (
            suscripcion
            if suscripcion
            else {"es_premium": False, "fecha_vencimiento": None, "plan": None}
        ),
        "friends_ids": amigos if amigos else [],
    }

    return col.insert_one(new_user)


# Profile Loading


def get_profile(col, username):
    """Return a full user profile document."""
    return col.find_one({"username": username})


# Progress Update


def update_progress_and_streak(col, username, idioma_id, xp_amount):
    """Atomic update of global XP, course XP and streak."""

    now = datetime.now(timezone.utc)

    update = {
        "$inc": {"total_xp": xp_amount},
        "$set": {"ultima_actividad": now},
    }

    update["$inc"][f"cursos.$[curso].xp_curso"] = xp_amount
    update["$inc"]["racha_actual"] = 1

    return col.update_one(
        {"username": username},
        update,
        array_filters=[{"curso.idioma_id": idioma_id}],
    )


# Privacy Update


def update_privacy(col, username, new_privacy):
    return col.update_one(
        {"username": username},
        {"$set": {"ajustes.privacidad_perfil": new_privacy}},
    )


# Subscription Management


def activate_plus(col, username, plan="mensual"):
    duration = timedelta(days=30) if plan == "mensual" else timedelta(days=365)

    return col.update_one(
        {"username": username},
        {
            "$set": {
                "suscripcion.es_premium": True,
                "suscripcion.plan": plan,
                "suscripcion.fecha_vencimiento": datetime.now(timezone.utc) + duration,
            }
        },
    )


def cancel_plus(col, username):
    return col.update_one(
        {"username": username},
        {
            "$set": {
                "suscripcion.es_premium": False,
                "suscripcion.plan": None,
                "suscripcion.fecha_vencimiento": None,
            }
        },
    )


#  Friends Management


def add_friend(col, username, friend_id):
    return col.update_one(
        {"username": username},
        {"$addToSet": {"friends_ids": friend_id}},
    )


def remove_friend(col, username, friend_id):
    return col.update_one(
        {"username": username},
        {"$pull": {"friends_ids": friend_id}},
    )


# Transaction Enrollment and Initialization


def enroll_and_init_course(client, username, idioma_id):
    session = client.start_session()
    col = client["duolingo_users"]["usuarios"]

    try:
        with session.start_transaction():
            col.update_one(
                {"username": username},
                {
                    "$push": {
                        "cursos": {
                            "idioma_id": idioma_id,
                            "xp_curso": 0,
                            "unidades_completadas": 0,
                        }
                    },
                    "$set": {"ultima_actividad": datetime.now(timezone.utc)},
                },
                session=session,
            )

        session.commit_transaction()

    except PyMongoError as e:
        session.abort_transaction()
        raise e
    finally:
        session.end_session()
