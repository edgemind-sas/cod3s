from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from models.user import UserInDB, UserPublic, UserPublicWithToken
from db.crud import get_user_by_email
from cod3s.utils.security import verify_password, create_access_token, hash_password
from db.crud import create_user, get_user_roles

router = APIRouter()

@router.post("/register", response_model=UserPublic)
async def register(user: UserInDB):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_BAD_REQUEST,
            detail="Email already registered"
        )
    
    new_user = await create_user(user, roles=user.roles)
    return UserPublic(**new_user.dict())


@router.post("/login", response_model=UserPublicWithToken)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_email(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    roles = await get_user_roles(user.id)
    access_token = create_access_token(data={"sub": user.email, "roles": roles})
    
    user_data_with_token = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "access_token": access_token,
        "token_type": "bearer"
    }

    return user_data_with_token
