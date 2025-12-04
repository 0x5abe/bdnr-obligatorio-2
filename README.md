# 📘 Escenario Duolingo

Este proyecto implementa **dos subsistemas** del obligatorio:

1. **Subsistema de Privacidad y Seguridad -> Redis Cluster** (clave-valor distribuido)
2. **Subsistema de Gestión de Usuarios y Perfiles -> MongoDB Sharded Cluster** (base documental)

A manera de ejemplo cada uno incluye una notebook Jupyter que demuestra sus patrones de acceso, modelo de datos y operaciones.

---

# ✔ Requisitos

- Docker + Docker Compose
- Python 3
- VSCode o JupyterLab para ejecutar las notebooks

---

# 🧪 Formas de ejecutar las notebooks

Podés elegir **una de estas dos formas**, válidas para ambos subsistemas:

### ✔ Opción A — Ejecutar en VSCode (recomendado)

VSCode + extensión **Jupyter**
Permite:

- ejecutar las notebooks sin contenedor extra
- usar el kernel Python del host
- acceder a los servicios de Redis y Mongo mediante `localhost`

### ✔ Opción B — Ejecutar en un contenedor Jupyter

Se levanta con el siguiente comando:

```bash
docker run -d --rm -p 8888:8888 -v ".\notebooks:/home/jovyan/work" --network duolingo-net jupyter/base-notebook:latest start-notebook.py --ServerApp.token=''
```

Acceder a:

```
http://localhost:8888
```

Dentro del contenedor, las notebooks pueden conectarse a Redis/Mongo a través de la red `duolingo-net`.

---

# 🌐 Red Docker (común a ambos subsistemas)

Crear la red una sola vez:

```bash
docker network create duolingo-net
```

Ambos clusters (Redis y Mongo) se conectan a esta red; por eso las notebooks, si corren en contenedor, pueden comunicarse correctamente.

---

# 🔐 Subsistema de Privacidad y Seguridad (Redis Cluster)

Implementa:

- autenticación
- tokens con TTL
- auditoría
- RBAC y métricas.

## Tecnologías

- **Redis Cluster** (6 nodos -> 3 masters + 3 slaves)
- **AOF + RDB**
- **Streams** para auditoría
- **Sets** para RBAC
- **HyperLogLog** para usuarios activos

---

## 1. Configurar IP del host

En Windows, Docker requiere que Redis Cluster anuncie la **IP del host** para poder conectarse desde el host.

Editar `.env`:

```
HOST_IP=192.168.1.x
```

---

## 2. Levantar Redis Cluster

```bash
docker compose -f docker-compose-redis.yml up -d
```

Esto:

- inicia los nodos
- crea el cluster si no existe
- deja datos persistentes en `redis-data/nodeX/`

---

## 3. Conexión en la notebook

### Si se ejecuta desde VSCode:

```python
r = connect_cluster([
    {"host": "localhost", "port": 7001},
    {"host": "localhost", "port": 7002},
    {"host": "localhost", "port": 7003},
])
```

### Si se ejecuta desde el contenedor Jupyter:

```python
r = connect_cluster([
    {"host": "redis-node-1", "port": 7001},
    {"host": "redis-node-2", "port": 7002},
    {"host": "redis-node-3", "port": 7003},
])
```

---

## 4. Notebook correspondiente

```
notebooks/security_subsystem.ipynb
```

Demuestra:

- Tokens con TTL
- RBAC
- Auditoría con streams
- Consentimientos y preferencias
- Anonimización asíncrona
- HyperLogLog
- Failover automático del cluster

---

# 👤 Subsistema de Gestión de Usuarios y Perfiles (MongoDB Sharded Cluster)

Implementa:

- perfiles
- progreso
- cursos
- racha
- suscripción plus
- privacidad
- amigos
- transacciones
- flexibilidad documental

---

## 1. Levantar MongoDB Sharded Cluster

```bash
docker compose -f docker-compose-mongo.yml up -d
```

Incluye:

- 1 shard con replica set (entorno de desarrollo)
- config server replicado (3 nodos)
- mongos router
- datos persistentes en `mongo-data/`
- expuesto en:

```
mongodb://localhost:27020
```

---

## 2. Conexión en la notebook

### Si se ejecuta desde VSCode:

```python
client = get_client("mongodb://localhost:27020")
```

### Si se ejecuta desde el contenedor Jupyter:

Docker Desktop permite usar:

```python
client = get_client("mongodb://mongos:270217")
```

---

## 3. Notebook correspondiente

```
notebooks/user_profile_subsystem.ipynb
```

Demuestra:

### ✔ Flexibilidad documental

- campos opcionales
- perfiles heterogéneos
- subdocumentos (cursos, privacidad, suscripción)
- arrays embebidos (amigos, cursos)

### ✔ Patrones de acceso del obligatorio

- carga completa del perfil (1 lectura)
- update XP + racha (atomic)
- update de privacidad
- índices sobre username / email / privacidad
- gestión de amigos
- transacción: enroll + initialize course

---

# 📁 Estructura del Proyecto

```
/
├─ docker-compose-redis.yml
├─ docker-compose-mongo.yml
├─ .env
│
├─ redis-data/
│   ├─ node1/ ... node6/
│
├─ mongo-data/
│
├─ notebooks/
│   ├─ security_subsystem.ipynb
│   ├─ security_setup.py
│   │
│   ├─ user_profile_subsystem.ipynb
│   ├─ user_profile_setup.py
│
└─ README.md
```
