# Escenario: Duolingo

## Implementación de subsistema de seguridad

En la carpeta notebooks se puede encontrar la implementación del subsistema de seguridad en el archivo `security_subsystem.ipynb`, la misma fue realizada con redis como se especificó previamente.

### Ejecución de notebook

Para probar la notebook se deben realizar los siguientes pasos:

- Ejecutar el servicio de **Docker**
- Iniciar redis mediante docker compose, con el comando `docker compose up`. Nota: Este comando también inicia un **servidor local de Jupyter** por si se desea testear la notebook con el mismo.
- Abrir la notebook en un entorno local de Jupyter (Ya sea con el servidor que inicia el archivo docker-compose o con la extensión **Jupyter** de VSCode).
- Configurar correctamente el hostname para la conexión. Si la notebook se ejecuta de forma local en VSCode el hostname se puede mantener en `localhost`, por otro lado si se ejecuta la notebook con el servidor de jupyter se debe cambiar al nombre del container: `redis`.
- Ejecutar los ejemplos de cada uno de los patrones de acceso.
