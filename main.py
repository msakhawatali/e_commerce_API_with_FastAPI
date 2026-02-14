# from re import template
from fastapi import FastAPI,Request, HTTPException, status, Depends
from starlette.requests import Request
from starlette.responses import HTMLResponse
from tortoise import models
from tortoise.contrib.fastapi import register_tortoise
from tortoise.signals import post_save
from models import *

#Authentication
from authentication import *
from fastapi.security import(OAuth2PasswordBearer, OAuth2PasswordRequestForm)
# signals
from tortoise.signals import post_save
from typing import List, Optional, Type
from tortoise import BaseDBAsyncClient
from emails import *

# response classes
from fastapi.responses import HTMLResponse

#image upload
from fastapi import File, UploadFile
import secrets
from fastapi.staticfiles import StaticFiles
from PIL import Image


#datetime
from datetime import datetime

#templates
from fastapi.templating import Jinja2Templates


app = FastAPI()


oath2_scheme = OAuth2PasswordBearer(tokenUrl= "token")


#static file setup config
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/token")
async def generate_token(request_form : OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(request_form.username, request_form.password)
    return {"access_token" : token, "token_type" : "bearer"}

async def get_current_user(token: str = Depends(oath2_scheme)):
    try:
        payload = jwt.decode(token, config_credential["SECRET"], algorithms=["HS256"])
        user = await User.get(id = payload.get("id")) 
    except:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED,
            detail="    Invalid username or password",
            headers={"WWW-Authenticate" : "Bearer"}
        )
    return await user



@app.post("/user/me")
async def user_login(user : user_pydanticIn = Depends(get_current_user)): # type: ignore
    business = await Business.get(owner= user)
    logo = business.logo #654564sdfsdf4dsf.png
    logo_path = "localhost:8000/static/images/"+logo

    return {
        "status" : "ok",
        "data" : {
            "username" : user.username,
            "email" : user.email,
            "verified" : user.is_verified,
            "joined_data" : user.join_data.strftime("%b %d %Y"),
            "logo" : logo_path
        }
    }


@post_save(User)
async def create_business(
    sender : "Type[User]",
    instance : User,
    created : bool,
    using_db : "Optional[BaseDBAsyncClient]",
    update_fields : List[str]
) -> None:
    
    if created :
        business_obj = await Business.create(
            business_name = instance.username, owner = instance
        )

        await business_pydantic.from_tortoise_orm(business_obj)
        # send the email 
        await send_email([instance.email], instance)


@app.post("/registration")
async def user_registrations(user: user_pydanticIn): # type: ignore
    user_info = user.dict(exclude_unset = True)
    user_info["password"] = get_hashed_password(user_info["password"])
    user_obj = await User.create(**user_info)
    new_user = await user_pydantic.from_tortoise_orm(user_obj)
    return{
        "status" : "ok",
        "data" : f"Hello {new_user.username}, thank for choosing our services. Please check your email inbox and click on the link to confirm your registration."
    }


templates = Jinja2Templates(directory="templates")

@app.get("/verification", response_class=HTMLResponse)
async def email_verification(request : Request, token : str):
    user = await very_token(token)

    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        return templates.TemplateResponse("verification.html", {"request" : request, "username": user.username})
    
    raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or expired token",
            headers= {"WWW-Authenticate": "Bearer"}
        )


@app.get("/")
def index():
    return {"Message": "Hello world"}


@app.post("/uploadfile/profile")
async def create_Upload_File (file : UploadFile = File(...), user: user_pydantic = Depends(get_current_user)): # type: ignore
    FILEPATA =  "./static/images"
    filename = file.filename
    #test.png >> ["test", "png"] 
    extenion = filename.split(".")[1]


    if extenion not in ["png","jpg"]:
        return {"status" : "error", "detail" : "File extension not allowed"}
    
    #/status/images/98dsf7g98s.png
    token_name = secrets.token_hex(10)+"."+extenion
    generate_name = FILEPATA + token_name
    file_content = await file.read()

    with open(generate_name, "wb") as file:
        file.write(file_content)


    #PILLOW
    img = Image.open(generate_name)
    img = img.resize(size=(200,200))
    img.save(generate_name)

    file.close()

    business = await Business.get(owner = user)
    owner = await business.owner


    if owner == user:
        business.logo = token_name
        await business.save()
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers= {"WWW-Authenticate": "Bearer"}
        )

    file_url = "localhost:8000" + generate_name[1:]
    return {"status" : "ok", "filename" : file_url}

@app.post("/uploadfile/product/{id}")
async def create_upload_file(id : int , file : UploadFile = File(...),user : user_pydantic = Depends(get_current_user)): # type: ignore
    FILEPATA =  "./static/images"
    filename = file.filename
    #test.png >> ["test", "png"] 
    extenion = filename.split(".")[1]


    if extenion not in ["png","jpg"]:
        return {"status" : "error", "detail" : "File extension not allowed"}
    
    #/status/images/98dsf7g98s.png
    token_name = secrets.token_hex(10)+"."+extenion
    generate_name = FILEPATA + token_name
    file_content = await file.read()

    with open(generate_name, "wb") as file:
        file.write(file_content)


    #PILLOW
    img = Image.open(generate_name)
    img = img.resize(size=(200,200))
    img.save(generate_name)

    file.close()

    product = await Product.get(id = id)
    business = await product.business
    owner = await business.owner


    if owner == user:
        product.product_image = token_name
        await product.save()

    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers= {"WWW-Authenticate": "Bearer"}
        )

    file_url = "localhost:8000" + generate_name[1:]
    return {"status" : "ok", "filename" : file_url}

#CRUD functionality


@app.post("/products")
async def add_new_product(product : product_pydanticIn, user : user_pydantic = Depends(get_current_user)): # type: ignore
    product = product.dict(exclude_unset = True)

    # to avoid division error by zero
    if product["original_price"] > 0:
        product["percentage_discount"] = ((product["original_price"] - product["new_price"]) / product["original_price"]) * 100

        product_obj = await Product.create(**product, business = user)
        product_obj = await product_pydantic.from_tortoise_orm(product_obj)

        return {"status" : "ok", "data" : product_obj}
    else:
        return {"status" : "error"}
    

@app.get("/product")
async def get_product():
    response = await product_pydantic.from_queryset(Product.all())
    return {"status" : "ok", "data" : response}


@app.get("/product/{id}")
async def get_product(id : int):
    product = await Product.get(id = id)
    business = await product.business
    owner = await business.owner
    response = await product_pydantic.from_queryset_single(Product.get(id = id))

    return{
        "status" : "ok",
        "data" : {
            "product_details" : response,
            "business_details" : {
                "name" : business.business_name,
                "city" : business.city,
                "region" : business.region,
                "decription" : business.decription,
                "logo" : business.logo,
                "owner_id" : owner.id,
                "email" : owner.email,
                "join_date" : owner.join_date.strftime("%b %d %Y") 

            }
        }
    }


@app.delete("/product"/{id})
async def delete_product(id : int, user : user_pydantic = Depends(get_current_user)): # type: ignore
    product = await Product.get(id = id)
    business = await product.business
    owner = await business.woner


    if user == owner:
        product.delete()

    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers= {"WWW-Authenticate": "Bearer"}
        )
    return {"status" : "ok"}


@app.put("/product/{id}")
async def update_product(id: int, update_info : product_pydanticIn, user : user_pydantic = Depends(get_current_user)): # type: ignore
    product = await Product.get(id = id)
    business = await product.business
    owner = await business.owner

    update_info = update_info.dict(exclude_unset = True)
    update_info["date_published"] = datetime.utcnow()

    if user == owner and update_info["origingal_price"] > 0:
        update_info["percentage-discount"] = ((update_info["original_price"] - update_info["new_orice"]) / update_info["original_ptice"]) * 100
        product = await product.update_from_dict(update_info)
        await product.save()
        response = await product_pydantic.from_tortoise_orm(product)
        return {"status": "ok", "data" : response}
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action or invalid user input",
            headers= {"WWW-Authenticate": "Bearer"}
        )
    

@app.put("/business/{id}")
async def update_business(id : int, update_business : business_pydanticIn, user : user_pydantic = Depends(get_current_user)): # type: ignore
    update_business = update_business.dict()

    business = await Business.get(id = id)
    business_owner = await business.woner


    if user == business_owner:
        await business.update_from_dict(update_business)
        business.save()
        response = await business_pydantic.from_tortoise_orm(business)
        return {"status": "ok", "data" : response}
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers= {"WWW-Authenticate": "Bearer"}
        )


register_tortoise(
    app,
    db_url="sqlite:/database.sqlite3",
    modules={"models" : ["models"]},
    generate_schemas=True,
    add_exception_handlers=True

)

@app.post("/cart/add/{product_id}")
async def add_to_cart(product_id: int, quantity: int = 1,
                      user: user_pydantic = Depends(get_current_user)):

    product = await Product.get(id=product_id)

    cart_item = await Cart.get_or_none(user=user, product=product)

    if cart_item:
        cart_item.quantity += quantity
        await cart_item.save()
    else:
        cart_item = await Cart.create(user=user, product=product, quantity=quantity)

    response = await cart_pydantic.from_tortoise_orm(cart_item)
    return {"status": "ok", "data": response}

@app.get("/cart")
async def view_cart(user: user_pydantic = Depends(get_current_user)):

    cart_items = await cart_pydantic.from_queryset(
        Cart.filter(user=user).prefetch_related("product")
    )

    return {"status": "ok", "data": cart_items}

@app.delete("/cart/remove/{product_id}")
async def remove_from_cart(product_id: int,
                           user: user_pydantic = Depends(get_current_user)):

    product = await Product.get(id=product_id)
    cart_item = await Cart.get_or_none(user=user, product=product)

    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    await cart_item.delete()

    return {"status": "ok", "message": "Item removed"}

@app.post("/order/checkout")
async def checkout(user: user_pydantic = Depends(get_current_user)):

    cart_items = await Cart.filter(user=user).prefetch_related("product")

    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_amount = 0

    for item in cart_items:
        total_amount += float(item.product.new_price) * item.quantity

    order = await Order.create(
        user=user,
        total_amount=total_amount
    )

    # Clear cart after order
    await Cart.filter(user=user).delete()

    response = await order_pydantic.from_tortoise_orm(order)

    return {"status": "ok", "data": response}

@app.get("/orders")
async def get_my_orders(user: user_pydantic = Depends(get_current_user)):

    orders = await order_pydantic.from_queryset(
        Order.filter(user=user)
    )

    return {"status": "ok", "data": orders}


@post_save(Order)
async def order_status_change(
    sender,
    instance: Order,
    created: bool,
    using_db,
    update_fields
):
    if not created and instance.status == "shipped":
        print(f"Order {instance.id} has been shipped.")
        # Yahan future me email bhi bhej sakte ho
