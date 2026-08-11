# FirstFoundry Streamlit App

Interfaz local para crear, consultar y continuar conversaciones persistentes del agente `FirstFoundry`.

## Estructura recomendada

Coloca `app.py` y `requirements.txt` en la raíz de tu repositorio:

```text
AI_Agent_Microsoft01/
├── .venv/
├── Azure_Notebooks/
├── Database/
│   └── conversations.json
├── app.py
└── requirements.txt
```

La aplicación detectará automáticamente `Database/conversations.json`.

## 1. Abrir PowerShell y activar el entorno

```powershell
cd C:\Users\Ricardo\Documents\GitHub\AI_Agent_Microsoft01
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. Instalar las dependencias

```powershell
python -m pip install -r requirements.txt
```

## 3. Comprobar la autenticación de Azure

```powershell
az account show --output table
```

Si la sesión ha caducado:

```powershell
az login
az account set --subscription "Azure subscription 1"
```

## 4. Ejecutar la aplicación

```powershell
python -m streamlit run app.py
```

Streamlit abrirá normalmente `http://localhost:8501` en el navegador.

## Qué hace esta primera versión

- Lee las conversaciones de `Database/conversations.json`.
- Muestra el historial de cada conversación desde Microsoft Foundry.
- Crea conversaciones nuevas y las registra localmente.
- Envía mensajes al agente y actualiza automáticamente `last_response_id`.
- Mantiene el contexto al volver a seleccionar una conversación.

## Coste

Abrir la aplicación o consultar el historial no genera una respuesta del modelo. Crear una conversación vacía tampoco invoca el modelo. El consumo se produce al enviar un mensaje y generar una respuesta; las herramientas configuradas en el agente pueden tener costes adicionales.

## Límite de esta versión

La interfaz muestra hasta 100 elementos del historial por conversación. Este límite se puede sustituir más adelante por paginación completa.
