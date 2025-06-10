import pymysql
import os 
pymysql.install_as_MySQLdb()
from flask import Flask,render_template,request,session,redirect,url_for,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import login_user,logout_user,login_manager,LoginManager
from flask_login import login_required,current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import session


# MY db connection
local_server= True
app = Flask(__name__)
app.secret_key='harshithbhaskar'


# this is for getting unique user access
login_manager=LoginManager(app)
login_manager.login_view='login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# app.config['SQLALCHEMY_DATABASE_URL']='mysql://username:password@localhost/databas_table_name'
app.config['SQLALCHEMY_DATABASE_URI']='mysql+pymysql://root:@localhost/farmers'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db=SQLAlchemy(app)

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'  # create this folder in your project
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# here we will create db models that is tables
class Test(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(100))

class Farming(db.Model):
    fid=db.Column(db.Integer,primary_key=True)
    farmingtype=db.Column(db.String(100))


class AddAgroProduct(db.Model):
    __tablename__ = 'addagroproducts'  
    pid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False) 
    email = db.Column(db.String(100))
    productname = db.Column(db.String(100))
    productdesc = db.Column(db.String(500))
    price = db.Column(db.Float)
    image_filename = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Relationship (optional but useful)
    user = db.relationship('User', backref='products')


class Trig(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    fid=db.Column(db.String(100))
    action=db.Column(db.String(100))
    timestamp=db.Column(db.String(100))


class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(50))
    email=db.Column(db.String(50),unique=True)
    password=db.Column(db.String(1000))
    role = db.Column(db.String(20))

class Register(db.Model):
    rid=db.Column(db.Integer,primary_key=True)
    farmername=db.Column(db.String(50))
    adharnumber=db.Column(db.String(50))
    age=db.Column(db.Integer)
    gender=db.Column(db.String(50))
    phonenumber=db.Column(db.String(50))
    address=db.Column(db.String(50))
    farming=db.Column(db.String(50))

    

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/farmerdetails')
@login_required
def farmerdetails():
    # query=db.engine.execute(f"SELECT * FROM `register`") 
    query=Register.query.all()
    return render_template('farmerdetails.html',query=query)

# For workers to see only their products
@app.route('/agroproducts')
@login_required
def agroproducts():
    if current_user.role == 'worker':
        products = AddAgroProduct.query.filter_by(user_id=current_user.id).all()
    else:  # customers see all products
        products = AddAgroProduct.query.all()
    return render_template('agroproducts.html', query=products)


# ADD TO CART
@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    if current_user.role != 'customer':
        abort(403)

    product = AddAgroProduct.query.get_or_404(product_id)

    # Initialize cart in session if it doesn't exist
    if 'cart' not in session or not isinstance(session['cart'], list):
        session['cart'] = []

    cart = session['cart']

    # Ensure all cart items are dicts (cleaning legacy bad data)
    cart = [item for item in cart if isinstance(item, dict)]

    # Check if product already in cart
    product_exists = False
    for item in cart:
        if item.get('product_id') == product_id:
            item['quantity'] += 1
            product_exists = True
            break

    if not product_exists:
        cart.append({
            'product_id': product_id,
            'quantity': 1
        })

    session['cart'] = cart
    session.modified = True  # make sure changes are saved

    print("Cart after adding:", session.get('cart'))

    flash(f'{product.productname} added to cart!', 'success')
    return redirect(url_for('agroproducts'))



@app.route('/cart')
@login_required
def view_cart():
    if current_user.role != 'customer':
        abort(403)
    
    cart_items = []
    total = 0
    
    # Get products from cart in session
    if 'cart' in session:
        for item in session['cart']:
            if isinstance(item, dict):
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
            elif isinstance(item, int):
                product_id = item
                quantity = 1
            else:
                print("Skipping unexpected cart item:", item)
                continue

            product = AddAgroProduct.query.get(product_id)
            if product:
                item_total = product.price * quantity
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'item_total': item_total
                })
                total += item_total


    
    return render_template('add_to_cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    if current_user.role != 'customer':
        abort(403)
    
    if 'cart' in session:
        cart = session['cart']
        # Find and remove the item
        for i, item in enumerate(cart):
            if item['product_id'] == product_id:
                product = AddAgroProduct.query.get_or_404(product_id)
                flash(f'{product.productname} removed from cart!', 'info')
                del cart[i]
                break
        session['cart'] = cart
    
    return redirect(url_for('view_cart'))

@app.route('/update_cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    if current_user.role != 'customer':
        abort(403)
    
    new_quantity = int(request.form.get('quantity', 1))
    if new_quantity < 1:
        flash('Quantity must be at least 1', 'danger')
        return redirect(url_for('view_cart'))
    
    if 'cart' in session:
        cart = session['cart']
        for item in cart:
            if item['product_id'] == product_id:
                item['quantity'] = new_quantity
                break
        session['cart'] = cart
        flash('Cart updated successfully!', 'success')
    
    return redirect(url_for('view_cart'))

@app.route('/clear_cart')
@login_required
def clear_cart():
    session.pop('cart', None)
    flash("Cart has been cleared.", "info")
    return redirect(url_for('view_cart'))



@app.route('/checkout')
@login_required
def checkout():
    # Implement your checkout logic here
    pass

@app.route('/addagroproduct', methods=['POST','GET'])
@login_required
def addagroproduct():
    if request.method == "POST":
        # Get form data (don't get username/email from form - use current_user)
        productname = request.form.get('productname')
        productdesc = request.form.get('productdesc')
        price = request.form.get('price')
        
        # Validate required fields
        if not all([productname, productdesc, price]):
            flash('Please fill all required fields', 'danger')
            return redirect(request.url)
        
        try:
            price = float(price)  # Convert price to float
            if price <= 0:
                flash('Price must be greater than 0', 'danger')
                return redirect(request.url)
        except ValueError:
            flash('Invalid price format', 'danger')
            return redirect(request.url)
        
        # Handle file upload
        if 'productimage' not in request.files:
            flash('No image selected', 'danger')
            return redirect(request.url)
            
        file = request.files['productimage']
        
        if file.filename == '':
            flash('No image selected', 'danger')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = secure_filename(file.filename)
            unique_filename = f"{current_user.username}_{timestamp}_{original_filename}"
            
            # Ensure upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            try:
                # Save the file
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                
                # Create product with current user's info
                new_product = AddAgroProduct(
                    username=current_user.username,
                    email=current_user.email,
                    productname=productname,
                    productdesc=productdesc,
                    price=price,
                    image_filename=unique_filename,
                )
                
                db.session.add(new_product)
                db.session.commit()
                flash("Product Added Successfully", "success")
                return redirect(url_for('agroproducts'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving product: {str(e)}', 'danger')
                return redirect(request.url)
                
        else:
            flash('Allowed image types are: png, jpg, jpeg, gif', 'danger')
            return redirect(request.url)
    
    # GET request - show form
    return render_template('addagroproducts.html')

@app.route('/triggers')
@login_required
def triggers():
    # query=db.engine.execute(f"SELECT * FROM `trig`") 
    query=Trig.query.all()
    return render_template('triggers.html',query=query)

@app.route('/addfarming',methods=['POST','GET'])
@login_required
def addfarming():
    if request.method=="POST":
        farmingtype=request.form.get('farming')
        query=Farming.query.filter_by(farmingtype=farmingtype).first()
        if query:
            flash("Farming Type Already Exist","warning")
            return redirect('/addfarming')
        dep=Farming(farmingtype=farmingtype)
        db.session.add(dep)
        db.session.commit()
        flash("Farming Addes","success")
    return render_template('farming.html')




@app.route("/delete/<string:rid>",methods=['POST','GET'])
@login_required
def delete(rid):
    # db.engine.execute(f"DELETE FROM `register` WHERE `register`.`rid`={rid}")
    post=Register.query.filter_by(rid=rid).first()
    db.session.delete(post)
    db.session.commit()
    flash("Slot Deleted Successful","warning")
    return redirect('/farmerdetails')

@app.route('/delete/<int:pid>')
@login_required
def delete_product(pid):
    try:
        # Get product using correct model name
        product = AddAgroProduct.query.get_or_404(pid)
        
        # Verify ownership (if needed)
        if product.email != current_user.email:
            flash("You can only delete your own products", "danger")
            return redirect(url_for('agroproducts'))
        
        # Delete the product
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting product: {str(e)}", "danger")
    
    return redirect(url_for('agroproducts'))


@app.route("/edit/<string:rid>",methods=['POST','GET'])
@login_required
def edit(rid):
    # farming=db.engine.execute("SELECT * FROM `farming`") 
    if request.method=="POST":
        farmername=request.form.get('farmername')
        adharnumber=request.form.get('adharnumber')
        age=request.form.get('age')
        gender=request.form.get('gender')
        phonenumber=request.form.get('phonenumber')
        address=request.form.get('address')
        farmingtype=request.form.get('farmingtype')     
        # query=db.engine.execute(f"UPDATE `register` SET `farmername`='{farmername}',`adharnumber`='{adharnumber}',`age`='{age}',`gender`='{gender}',`phonenumber`='{phonenumber}',`address`='{address}',`farming`='{farmingtype}'")
        post=Register.query.filter_by(rid=rid).first()
        print(post.farmername)
        post.farmername=farmername
        post.adharnumber=adharnumber
        post.age=age
        post.gender=gender
        post.phonenumber=phonenumber
        post.address=address
        post.farming=farmingtype
        db.session.commit()
        flash("Slot is Updates","success")
        return redirect('/farmerdetails')
    posts=Register.query.filter_by(rid=rid).first()
    farming=Farming.query.all()
    return render_template('edit.html',posts=posts,farming=farming)

@app.route('/editagro/<int:pid>')
@login_required
def edit_agro(pid):
    product = AddAgroProduct.query.get_or_404(pid)  # Changed to use AddAgroProduct
    return render_template('editagroproduct.html', product=product)

@app.route('/updateagroproduct/<int:pid>', methods=['POST'])
@login_required
def update_product(pid):
    product = AddAgroProduct.query.get_or_404(pid)
    
    # Verify ownership
    if product.email != current_user.email:
        flash("Unauthorized action", "danger")
        return redirect(url_for('agroproducts'))
    
    try:
        # Update fields from form data
        product.productname = request.form.get('productname')
        product.productdesc = request.form.get('productdesc')
        product.price = request.form.get('price')
        
        # Handle image upload if a new file was provided
        if 'productimage' in request.files:
            file = request.files['productimage']
            if file.filename != '':
                # Save new file and update filename
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                product.image_filename = filename
        
        db.session.commit()
        flash("Product updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating product: {str(e)}", "danger")
    
    return redirect(url_for('agroproducts'))


@app.route('/signup',methods=['POST','GET'])
def signup():
    if request.method == "POST":
        username=request.form.get('username')
        email=request.form.get('email')
        password=request.form.get('password')
        role = request.form.get('role')
        print(username,email,password,role)
        user=User.query.filter_by(email=email).first()
        if user:
            flash("Email Already Exist","warning")
            return render_template('/signup.html')
        # encpassword=generate_password_hash(password)

        # new_user=db.engine.execute(f"INSERT INTO `user` (`username`,`email`,`password`) VALUES ('{username}','{email}','{encpassword}')")

        # this is method 2 to save data in db
        newuser = User(username=username, email=email, password=password, role=role)
        db.session.add(newuser)
        db.session.commit()
        flash("Signup Succes Please Login","success")
        return render_template('login.html')

          

    return render_template('signup.html')

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user:
            login_user(user)
            
            # Redirect based on role
            if user.role == "admin":
                return redirect(url_for('admin_dashboard'))
            elif user.role == "customer":
                return redirect(url_for('customer_dashboard'))
            elif user.role == "worker":
                return redirect(url_for('worker_dashboard'))

        flash("Invalid credentials", "warning")
        return render_template('login.html')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout SuccessFul","warning")
    return redirect(url_for('login'))



@app.route('/register',methods=['POST','GET'])
@login_required
def register():
    farming=Farming.query.all()
    if request.method=="POST":
        farmername=request.form.get('farmername')
        adharnumber=request.form.get('adharnumber')
        age=request.form.get('age')
        gender=request.form.get('gender')
        phonenumber=request.form.get('phonenumber')
        address=request.form.get('address')
        farmingtype=request.form.get('farmingtype')     
        query=Register(farmername=farmername,adharnumber=adharnumber,age=age,gender=gender,phonenumber=phonenumber,address=address,farming=farmingtype)
        db.session.add(query)
        db.session.commit()
        # query=db.engine.execute(f"INSERT INTO `register` (`farmername`,`adharnumber`,`age`,`gender`,`phonenumber`,`address`,`farming`) VALUES ('{farmername}','{adharnumber}','{age}','{gender}','{phonenumber}','{address}','{farmingtype}')")
        # flash("Your Record Has Been Saved","success")
        return redirect('/farmerdetails')
    return render_template('farmer.html',farming=farming)

@app.route('/test')
def test():
    try:
        Test.query.all()
        return 'My database is Connected'
    except:
        return 'My db is not Connected'

@app.route('/worker_dashboard')
def worker_dashboard():
    return render_template('worker_dashboard.html') 

@app.route('/customer_dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html') 

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html') 

@app.route('/debug_user')
def debug_user():
    return {
        'authenticated': current_user.is_authenticated,
        'username': current_user.username if current_user.is_authenticated else None,
        'role': current_user.role if current_user.is_authenticated else None,
        'session': dict(session)
    }
    
@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:  # Assuming you have an is_admin flag
        abort(403)
    all_products = AddAgroProduct.query.all()
    return render_template('admin_products.html', products=all_products)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app.run(debug=True)    
