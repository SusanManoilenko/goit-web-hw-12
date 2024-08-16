from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import timedelta
import crud, schemas, auth
from database import get_db, engine
from models import Base

# Ініціалізація FastAPI додатку
app = FastAPI()

# Створення всіх таблиць у базі даних
Base.metadata.create_all(bind=engine)

# Налаштування OAuth2PasswordBearer для авторизації
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Функція для отримання поточного користувача за допомогою JWT токена
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

# Маршрут для реєстрації нового користувача
@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=409, detail="Email already registered")
    return crud.create_user(db=db, user=user)

# Маршрут для отримання JWT токенів (вхід користувача)
@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    refresh_token = auth.create_refresh_token(data={"sub": user.email})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

# Маршрут для отримання всіх контактів користувача
@app.get("/contacts/", response_model=list[schemas.Contact])
def read_contacts(skip: int = 0, limit: int = 10, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    contacts = crud.get_contacts(db=db, skip=skip, limit=limit)
    return [contact for contact in contacts if contact.owner_id == current_user.id]

# Маршрут для створення нового контакту
@app.post("/contacts/", response_model=schemas.Contact, status_code=status.HTTP_201_CREATED)
def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    return crud.create_contact(db=db, contact=contact, user_id=current_user.id)

# Маршрут для оновлення існуючого контакту
@app.put("/contacts/{contact_id}", response_model=schemas.Contact)
def update_contact(contact_id: int, contact: schemas.ContactCreate, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_contact = crud.get_contact(db=db, contact_id=contact_id)
    if db_contact is None or db_contact.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contact not found or not authorized to update this contact")
    return crud.update_contact(db=db, contact=contact, contact_id=contact_id)

# Маршрут для видалення контакту
@app.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    db_contact = crud.get_contact(db=db, contact_id=contact_id)
    if db_contact is None or db_contact.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contact not found or not authorized to delete this contact")
    crud.delete_contact(db=db, contact_id=contact_id)
    return {"message": "Contact deleted successfully"}

# Маршрут для пошуку контактів за ім'ям, прізвищем або email
@app.get("/contacts/search/", response_model=list[schemas.Contact])
def search_contacts(query: str, db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    contacts = crud.search_contacts(db=db, query=query)
    return [contact for contact in contacts if contact.owner_id == current_user.id]

# Маршрут для отримання контактів з днями народження на найближчі 7 днів
@app.get("/contacts/upcoming-birthdays/", response_model=list[schemas.Contact])
def upcoming_birthdays(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_current_user)):
    contacts = crud.get_upcoming_birthdays(db=db)
    return [contact for contact in contacts if contact.owner_id == current_user.id]