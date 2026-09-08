# OAuth / IdP deployment для v3.0

Этот документ описывает staging и production boundary между ChatGPT, внешним OAuth 2.1 identity provider и read-only MCP resource server Regulator.

Это инструкция для сопровождающего проекта, а не часть пользовательской установки. Для конечного пользователя сценарий v3.0 не меняется:

```text
GitHub Release ZIP
        ↓
ChatGPT Web
        ↓
quota-sensitive момент
        ↓
Connect / Auth внутри ChatGPT
```

Пользователь не настраивает IdP, не копирует client secret и не запускает локальный сервис.

## Почему authorization server внешний

Regulator проверяет access token на своей стороне, но не выпускает OAuth tokens и не хранит базу пользователей или ключи подписи IdP.

```text
ChatGPT
   ↓ OAuth 2.1 + PKCE S256
established IdP
   ↓ scoped access token
Regulator /mcp
   ↓ OIDC/JWKS verification
trusted subject
```

Для первого staging-прохода выбран Auth0. Это deployment profile, а не зависимость core: `idp_preflight.py`, `oidc_token_verifier.py` и `production_runtime.py` работают с контрактом OAuth/OIDC metadata и не импортируют Auth0 SDK.

## Что должно быть известно до запуска

Нужны три HTTPS URL:

```text
REGULATOR_OIDC_ISSUER_URL
REGULATOR_OIDC_METADATA_URL
REGULATOR_MCP_RESOURCE_URL
```

`REGULATOR_MCP_RESOURCE_URL` — канонический resource identifier MCP и одновременно ожидаемый audience access token. Для текущего transport он заканчивается на `/mcp`.

По умолчанию:

```text
REGULATOR_OIDC_CLIENT_REGISTRATION_MODE=cimd
REGULATOR_OIDC_REQUIRE_RFC9207_ISSUER_IDENTIFICATION=true
```

Поддерживаемые registration modes:

```text
cimd
dcr
predefined
```

`predefined` разрешается только после отдельного review и явной настройки `REGULATOR_OIDC_PREDEFINED_CLIENT_REVIEWED=true`.

## Preflight перед регистрацией в ChatGPT

Запуск:

```bash
python3 plugin/idp_preflight.py \
  --issuer "$REGULATOR_OIDC_ISSUER_URL" \
  --metadata-url "$REGULATOR_OIDC_METADATA_URL" \
  --resource "$REGULATOR_MCP_RESOURCE_URL"
```

PASS означает только то, что discovery metadata согласуется с нашим static contract:

- exact issuer;
- HTTPS authorization/token/JWKS endpoints;
- PKCE `S256`;
- состояние advertisement для `quota:read`;
- совместимый token endpoint auth method;
- выбранный client registration mode;
- RFC 9207 issuer identification, если он включён в deployment policy.

`quota:read` остаётся обязательным permission target API, но его отсутствие в authorization-server `scopes_supported` не является static failure. Некоторые IdP, включая наблюдаемый Auth0 custom API profile, не публикуют custom API permissions в OIDC discovery. Preflight в таком случае возвращает `required_scope_advertisement=NOT_ADVERTISED`, а реальный authorize/token E2E обязан доказать, что `quota:read` был запрошен и присутствует в выданном access token.

PASS не доказывает полноценный OAuth flow. До release отдельно проверяются:

```text
required_scope_requested_and_granted_in_access_token
resource_parameter_echoed_and_bound_to_access_token_audience
exact_chatgpt_redirect_uri_allowlisted
real_chatgpt_connection_registration
connect_authorize_token_exchange
```

Хороший discovery document не заменяет E2E.

## Auth0 staging profile

Первый поддерживаемый staging profile описан в:

```text
deployment/auth0-staging.example.json
```

В репозитории нет tenant domain, client secret, signing key или access token.

Для реального development tenant нужно добиться, чтобы metadata и issued access token соответствовали контракту:

1. `issuer` совпадает посимвольно с `REGULATOR_OIDC_ISSUER_URL`.
2. `code_challenge_methods_supported` содержит `S256`.
3. `quota:read` существует в Custom API permissions и разрешён для third-party user-delegated access; его наличие в OIDC `scopes_supported` считается дополнительным evidence, а не обязательным discovery field.
4. Выбранный registration mode реально поддерживается.
5. Если включён RFC 9207 gate, authorization responses действительно возвращают exact `iss`, а metadata публикует `authorization_response_iss_parameter_supported=true`.
6. `resource`, который ChatGPT передаёт в authorization/token request, привязывается к access token для нашего MCP, обычно через `aud`.
7. Exact redirect URI копируется из ChatGPT app management и добавляется в allowlist IdP. Его не нужно угадывать или хардкодить заранее.
8. Выданный access token содержит `quota:read`; отсутствие scope в token — fail независимо от static discovery.

## Resource server runtime

После успешного live preflight deployment собирает MCP runtime через:

```python
from plugin.production_runtime import (
    ProductionRuntimeConfig,
    build_production_app,
)

config = ProductionRuntimeConfig.from_environment()
app = build_production_app(quota_handler, config)
```

Resource server получает только настройки проверки access token. OAuth client secrets в этом процессе запрещены:

```text
REGULATOR_OIDC_CLIENT_SECRET
REGULATOR_OAUTH_CLIENT_SECRET
```

Если такая переменная появляется, composition падает до запуска MCP.

Это намеренное разделение ответственности. Client registration и authorization server живут у IdP; `/mcp` проверяет уже выданный bearer token.

## Регистрация ChatGPT connection

`.app.json` не создаётся до реальной регистрации.

Порядок:

```text
public HTTPS /mcp
        ↓
live IdP preflight PASS
        ↓
register MCP connection in ChatGPT
        ↓
copy exact redirect URI to IdP allowlist
        ↓
complete Connect/Auth E2E
        ↓
receive real plugin_asdk_app...
        ↓
add .app.json in a reviewed Git commit
```

Технический ID нельзя придумывать. Если ChatGPT ещё не вернул `plugin_asdk_app...`, package остаётся без `.app.json`.

## Что считается закрытым staging gate

Staging IdP/MCP gate закрывается только при наличии evidence для всех пунктов:

```text
IDP_DISCOVERY_PREFLIGHT=PASS
PKCE_S256=PASS
REQUIRED_SCOPE_GRANT=PASS
RESOURCE_TO_AUDIENCE_BINDING=PASS
RFC9207_ISSUER_IDENTIFICATION=PASS
EXACT_CHATGPT_REDIRECT_ALLOWLISTED=PASS
MCP_BEARER_VERIFICATION=PASS
CONNECT_AUTH_TOKEN_EXCHANGE=PASS
REGISTERED_CHATGPT_CONNECTION_ID=<real plugin_asdk_app...>
```

После этого можно переходить к subject-to-Codex-account binding E2E, refresh/revoke/logout, production vault/lease deployment и security review.
