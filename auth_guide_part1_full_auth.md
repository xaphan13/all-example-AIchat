# Руководство по аутентификации и авторизации в современных веб-приложениях (Часть 1: Полноценные системы аутентификации)

В современной веб-разработке безопасность и правильная аутентификация пользователей являются ключевыми аспектами любого приложения. В данном цикле статей мы рассмотрим различные подходы к реализации аутентификации и сессий на примерах 6 реальных проектов, представленных в данном репозитории.

В первой части мы подробно разберем проекты с полноценной регистрацией, авторизацией пользователей на основе JWT и разделением прав доступа. В качестве примеров мы возьмем проекты **AI-Chatbot** и **rag-knowledge-base-chatbot**.

---

## 1. Использование библиотеки FastAPI-Users (на примере AI-Chatbot)

В проекте **AI-Chatbot** для реализации аутентификации используется мощная и расширяемая библиотека `fastapi-users`. Она предоставляет готовые маршруты для регистрации, входа, сброса пароля и управления пользователями.

### Описание подхода

Приложение поддерживает два способа аутентификации:
1. **JWT (JSON Web Token)** — используется преимущественно для API-клиентов.
2. **Cookies (Куки)** — используется для веб-браузеров, что позволяет более безопасно сохранять сессию при переходах по страницам веб-интерфейса.

### Код: Настройка стратегий и транспортов

В файле `AI-Chatbot/app/api/v1/users.py` можно увидеть, как гибко настраивается `fastapi-users`:

```python
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)

# Функция для генерации JWT токена
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

# JWT аутентификация (Bearer token)
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
jwt_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Куки аутентификация для веб-браузеров
cookie_transport = CookieTransport(cookie_max_age=3600)
cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
```

Затем создается экземпляр `FastAPIUsers`, в который передаются оба настроенных бэкенда:

```python
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [jwt_auth_backend, cookie_auth_backend],
)

# Получение роутеров
login_router = fastapi_users.get_auth_router(cookie_auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
```

Такой подход позволяет веб-интерфейсу (на базе шаблонов Jinja2, находящихся в `AI-Chatbot/app/templates/`) отправлять логин и пароль и получать куки `fastapiusersauth`, которые браузер автоматически прикрепляет к следующим запросам.

---

## 2. Кастомная JWT аутентификация и API-токены (на примере rag-knowledge-base-chatbot)

В то время как `fastapi-users` дает много функционала "из коробки", иногда требуется более тонкая настройка и собственная реализация. В проекте **rag-knowledge-base-chatbot** аутентификация написана с нуля. Она включает в себя проверку паролей, JWT сессии и систему ролей (Admin, User), а также возможность генерировать статические API-токены для интеграций.

### Роутер логина и создание JWT

В файле `rag-knowledge-base-chatbot/app/api/routes/auth.py` реализован классический метод `/login`, который проверяет хэш пароля и возвращает `access_token`:

```python
@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await get_user_by_username(db, body.username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    # Создание JWT токена
    token = create_access_token(str(user.id), user.role)
    return LoginResponse(
        access_token=token,
        user={"id": user.id, "username": user.username, "role": user.role},
    )
```

### Защита роутов (Dependencies)

Для того чтобы защитить определенные эндпоинты, используются `Depends`. Метод `get_current_user_jwt` извлекает токен из заголовка `Authorization: Bearer <token>`, валидирует его и достает пользователя из базы данных.

```python
_bearer = HTTPBearer(auto_error=False)

async def get_current_user_jwt(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Bearer token required")

    payload = _user_from_token(credentials.credentials)
    # ... получение юзера из БД
    return user
```

### Разграничение ролей (Role-Based Access Control)

Для административных функций в приложении используется дополнительная зависимость `require_admin`, которая проверяет роль текущего пользователя. Это элегантный способ ограничить доступ к определенным частям API.

```python
def require_admin(user: Annotated[User, Depends(get_current_user_jwt)]) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
```

### Управление API-токенами

Помимо классической JWT сессии, приложение позволяет пользователям генерировать API-токены (например, для использования в скриптах). При создании токена он возвращается пользователю **только один раз**, а в БД сохраняется только его хэш.

```python
@router.post("/tokens", response_model=ApiTokenCreateResponse)
async def create_token(
    body: ApiTokenCreate,
    user: Annotated[User, Depends(get_current_user_jwt)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    plain, token_hash, prefix = generate_api_token()
    token = ApiToken(
        user_id=user.id,
        name=body.name,
        token_hash=token_hash,
        token_prefix=prefix,
        scopes="api",
    )
    db.add(token)
    await db.flush()
    return ApiTokenCreateResponse(token=plain, ...)  # plain-токен показывается 1 раз
```

## Вывод по Части 1

Оба подхода имеют свои плюсы. Использование готовых библиотек, таких как `fastapi-users`, сильно ускоряет разработку и закрывает большинство вопросов безопасности, включая работу с куками. С другой стороны, написание собственной логики дает полный контроль над процессом, позволяет легко добавлять систему ролей и дополнительные фичи вроде генерации API-токенов.

В [следующей части](auth_guide_part2_websockets_sessions.md) мы поговорим о том, как реализовать анонимные сессии и аутентификацию в WebSockets на примерах проектов `GroqStreamChain` и `Quorum`.
