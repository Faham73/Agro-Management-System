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
from sqlalchemy import text
from flask import send_from_directory
from flask import request, flash, redirect, url_for, render_template
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort


# MY db connection
local_server= True
app = Flask(__name__)
app.secret_key='faham73'


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

class OrderTracking(db.Model):
    __tablename__ = 'order_tracking'
    
    tracking_id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id'))
    status = db.Column(db.String(20))
    update_time = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

#admin pages


@app.route('/farmerdetails')
@login_required
def farmerdetails():
    if current_user.role != 'admin':
        abort(403)
    
    # Fetch only workers from the user table
    workers = db.session.execute(
        text("SELECT * FROM user WHERE role = 'worker'")
    ).fetchall()
    return render_template('farmerdetails.html', workers=workers)

@app.route('/edit_worker/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_worker(id):
    if current_user.role != 'admin':
        abort(403)
    
    worker = db.session.execute(
        text("SELECT * FROM user WHERE id = :id AND role = 'worker'"),
        {'id': id}
    ).fetchone()
    
    if not worker:
        abort(404)
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        
        # Validate role to prevent changing to admin
        if role not in ['worker', 'customer']:
            flash('Invalid role selected', 'danger')
            return redirect(url_for('edit_worker', id=id))
        
        db.session.execute(
            text("UPDATE user SET username = :username, email = :email, role = :role WHERE id = :id"),
            {'username': username, 'email': email, 'role': role, 'id': id}
        )
        db.session.commit()
        flash('Worker updated successfully', 'success')
        return redirect(url_for('farmerdetails'))
    
    return render_template('edit_worker.html', worker=worker)

@app.route('/delete_worker/<int:id>')
@login_required
def delete_worker(id):
    if current_user.role != 'admin':
        abort(403)
    
    # Ensure we're only deleting workers
    result = db.session.execute(
        text("DELETE FROM user WHERE id = :id AND role = 'worker'"),
        {'id': id}
    )
    db.session.commit()
    
    if result.rowcount == 0:
        flash('Worker not found or cannot be deleted', 'danger')
    else:
        flash('Worker deleted successfully', 'success')
    
    return redirect(url_for('farmerdetails'))


@app.route('/order_management')
@login_required
def order_management():
    if current_user.role != 'admin':
        abort(403)
    
    status_filter = request.args.get('status')
    
    query = """
    SELECT 
        p.payment_id,
        u.username as customer_name,
        u.id as customer_id,
        p.payment_date as order_date,
        SUM(oi.price * oi.quantity) as total_amount,
        (SELECT status FROM order_tracking 
         WHERE payment_id = p.payment_id 
         ORDER BY update_time DESC LIMIT 1) as status,
        COUNT(oi.order_item_id) as item_count,
        MAX(ot.update_time) as last_update
    FROM payments p
    JOIN user u ON p.user_id = u.id
    JOIN order_items oi ON p.payment_id = oi.payment_id
    LEFT JOIN order_tracking ot ON p.payment_id = ot.payment_id
    """
    
    params = {}
    if status_filter:
        query += " WHERE (SELECT status FROM order_tracking WHERE payment_id = p.payment_id ORDER BY update_time DESC LIMIT 1) = :status"
        params['status'] = status_filter
    
    query += " GROUP BY p.payment_id, u.username, u.id, p.payment_date ORDER BY p.payment_date DESC"
    
    try:
        result = db.session.execute(text(query), params)
        
        # Properly convert result to list of dictionaries
        orders = []
        for row in result:
            order = {
                'payment_id': row.payment_id,
                'customer_name': row.customer_name,
                'customer_id': row.customer_id,
                'order_date': row.order_date or datetime.now(),  # Handle None
                'total_amount': float(row.total_amount) if row.total_amount else 0.0,
                'status': row.status or 'processing',
                'item_count': row.item_count,
                'last_update': row.last_update or datetime.now()
            }
            orders.append(order)
            
        return render_template('order_management.html', 
                            orders=orders, 
                            current_filter=status_filter)
        
    except Exception as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/order_details/<int:payment_id>')
@login_required
def order_details(payment_id):
    # Verify order belongs to customer (unless admin)
    query = """
    SELECT p.*, u.username, u.email,
           (SELECT status FROM order_tracking 
            WHERE payment_id = p.payment_id 
            ORDER BY update_time DESC LIMIT 1) as status
    FROM payments p
    JOIN user u ON p.user_id = u.id
    WHERE p.payment_id = :payment_id
    """
    
    params = {'payment_id': payment_id}
    
    if current_user.role != 'admin':
        query += " AND p.user_id = :user_id"
        params['user_id'] = current_user.id
    
    order = db.session.execute(text(query), params).fetchone()
    
    if not order:
        abort(404)  # This will now work after adding the import
    
    items = db.session.execute(
        text("""
        SELECT oi.*, a.productname as product_name, a.price, a.image_filename
        FROM order_items oi
        JOIN addagroproducts a ON oi.product_id = a.pid
        WHERE oi.payment_id = :payment_id
        """),
        {'payment_id': payment_id}
    ).fetchall()
    
    return render_template('order_details.html', 
                         order=order, 
                         items=items,
                         is_admin=current_user.role == 'admin')
    
@app.route('/order_history')
@login_required
def order_history():
    orders = db.session.execute(
        text("""
        SELECT 
            p.payment_id, 
            p.payment_date, 
            p.total_amount,  # Changed from amount to total_amount
            (SELECT status FROM order_tracking 
             WHERE payment_id = p.payment_id 
             ORDER BY update_time DESC LIMIT 1) as status,
            COUNT(oi.order_item_id) as item_count
        FROM payments p
        JOIN order_items oi ON p.payment_id = oi.payment_id
        WHERE p.user_id = :user_id
        GROUP BY p.payment_id, p.payment_date, p.total_amount  # Added all non-aggregated columns
        ORDER BY p.payment_date DESC
        """),
        {'user_id': current_user.id}
    ).fetchall()
    
    return render_template('order_history.html', orders=orders)

# Order Status Update (for orders)
@app.route('/update_order_status/<int:payment_id>', methods=['POST'])
@login_required
def update_order_status(payment_id):
    if current_user.role not in ['admin', 'worker']:
        abort(403)
    
    new_status = request.form.get('status')  # Get status from form data
    valid_statuses = ['processing', 'shipped', 'delivered', 'cancelled']
    
    # Change from 'status' to 'new_status' in this check:
    if new_status not in valid_statuses:
        flash('Invalid status selected', 'danger')
        return redirect(url_for('order_details', payment_id=payment_id))
    
    try:
        db.session.execute(
            text("""
            INSERT INTO order_tracking (payment_id, status)
            VALUES (:payment_id, :status)
            """),
            {'payment_id': payment_id, 'status': new_status}
        )
        db.session.commit()
        flash(f'Status updated to {new_status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating status: {str(e)}', 'danger')
    
    return redirect(url_for('order_details', payment_id=payment_id))


# For workers to see only their products
@app.route('/agroproducts')
@login_required
def agroproducts():
    if current_user.role == 'worker':
        products = AddAgroProduct.query.filter_by(email=current_user.email).all()
    else:  # customers see all products
        products = AddAgroProduct.query.all()
    return render_template('agroproducts.html', query=products)




# ADD TO CART
@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    if current_user.role != 'customer':
        abort(403)

    # Get or create cart for user
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if not cart:
        db.session.execute(
            text("INSERT INTO carts (user_id) VALUES (:user_id)"),
            {'user_id': current_user.id}
        )
        db.session.commit()
        cart_id = db.session.execute(
            text("SELECT LAST_INSERT_ID()")
        ).fetchone()[0]
    else:
        cart_id = cart[0]

    # Check if product already in cart
    existing_item = db.session.execute(
        text("""
        SELECT cart_item_id, quantity 
        FROM cart_items 
        WHERE cart_id = :cart_id AND product_id = :product_id
        """),
        {'cart_id': cart_id, 'product_id': product_id}
    ).fetchone()

    if existing_item:
        # Update quantity if product exists
        db.session.execute(
            text("""
            UPDATE cart_items 
            SET quantity = quantity + 1 
            WHERE cart_item_id = :cart_item_id
            """),
            {'cart_item_id': existing_item[0]}
        )
    else:
        # Add new item to cart
        db.session.execute(
            text("""
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (:cart_id, :product_id, 1)
            """),
            {'cart_id': cart_id, 'product_id': product_id}
        )
    
    db.session.commit()

    product = AddAgroProduct.query.get_or_404(product_id)
    flash(f'{product.productname} added to cart!', 'success')
    return redirect(url_for('agroproducts'))

# VIEW CART
@app.route('/cart')
@login_required
def view_cart():
    if current_user.role != 'customer':
        abort(403)
    
    # Get user's cart
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    cart_items = []
    total = 0.0
    
    if cart:
        # Get all items in cart with product details using JOIN
        items = db.session.execute(
            text("""
            SELECT ci.quantity, p.pid, p.productname, p.price, p.image_filename, p.username
            FROM cart_items ci
            JOIN addagroproducts p ON ci.product_id = p.pid
            WHERE ci.cart_id = :cart_id
            """),
            {'cart_id': cart[0]}
        ).fetchall()

        for item in items:
            quantity = item[0]
            item_total = float(item[3]) * quantity
            cart_items.append({
                'product': {
                    'pid': item[1],
                    'productname': item[2],
                    'price': item[3],
                    'image_filename': item[4],
                    'username': item[5]
                },
                'quantity': quantity,
                'item_total': item_total
            })
            total += item_total
    
    return render_template('add_to_cart.html', cart_items=cart_items, total=total)

# REMOVE FROM CART
@app.route('/remove_from_cart/<int:product_id>')
@login_required
def remove_from_cart(product_id):
    if current_user.role != 'customer':
        abort(403)
    
    # Get user's cart
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if cart:
        # Get product name before deleting for flash message
        product = db.session.execute(
            text("""
            SELECT p.productname 
            FROM addagroproducts p
            WHERE p.pid = :product_id
            """),
            {'product_id': product_id}
        ).fetchone()

        # Delete the item
        db.session.execute(
            text("""
            DELETE FROM cart_items 
            WHERE cart_id = :cart_id AND product_id = :product_id
            """),
            {'cart_id': cart[0], 'product_id': product_id}
        )
        db.session.commit()

        if product:
            flash(f'{product[0]} removed from cart!', 'info')
    
    return redirect(url_for('view_cart'))

# UPDATE CART
@app.route('/update_cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    if current_user.role != 'customer':
        abort(403)
    
    new_quantity = int(request.form.get('quantity', 1))
    if new_quantity < 1:
        flash('Quantity must be at least 1', 'danger')
        return redirect(url_for('view_cart'))
    
    # Get user's cart
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if cart:
        db.session.execute(
            text("""
            UPDATE cart_items 
            SET quantity = :quantity 
            WHERE cart_id = :cart_id AND product_id = :product_id
            """),
            {'quantity': new_quantity, 'cart_id': cart[0], 'product_id': product_id}
        )
        db.session.commit()
        flash('Cart updated successfully!', 'success')
    
    return redirect(url_for('view_cart'))

# CLEAR CART
@app.route('/clear_cart')
@login_required
def clear_cart():
    if current_user.role != 'customer':
        abort(403)
    
    # Get user's cart
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if cart:
        db.session.execute(
            text("DELETE FROM cart_items WHERE cart_id = :cart_id"),
            {'cart_id': cart[0]}
        )
        db.session.commit()
        flash("Cart has been cleared.", "info")
    
    return redirect(url_for('view_cart'))

# CHECKOUT
@app.route('/checkout')
@login_required
def checkout():
    if current_user.role != 'customer':
        abort(403)
    
    # Get user's cart items
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if not cart:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('agroproducts'))

    # Get cart items with product details
    items = db.session.execute(
        text("""
        SELECT ci.quantity, p.pid, p.productname, p.price, p.image_filename
        FROM cart_items ci
        JOIN addagroproducts p ON ci.product_id = p.pid
        WHERE ci.cart_id = :cart_id
        """),
        {'cart_id': cart[0]}
    ).fetchall()

    # Calculate total
    total = sum(float(item[3]) * item[0] for item in items)
    
    return render_template('checkout.html', items=items, total=total)

@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    if current_user.role != 'customer':
        abort(403)
    
    # Get user's cart
    cart = db.session.execute(
        text("SELECT cart_id FROM carts WHERE user_id = :user_id"),
        {'user_id': current_user.id}
    ).fetchone()

    if not cart:
        flash('Your cart is empty!', 'danger')
        return redirect(url_for('agroproducts'))

    # Get cart items
    items = db.session.execute(
        text("""
        SELECT product_id, quantity, price 
        FROM cart_items ci
        JOIN addagroproducts p ON ci.product_id = p.pid
        WHERE ci.cart_id = :cart_id
        """),
        {'cart_id': cart[0]}
    ).fetchall()

    total = sum(float(item[2]) * item[1] for item in items)
    
    try:
        # Create payment record
        db.session.execute(
            text("""
            INSERT INTO payments (user_id, total_amount, payment_status)
            VALUES (:user_id, :total, 'completed')
            """),
            {'user_id': current_user.id, 'total': total}
        )
        db.session.commit()
        
        # Get the payment ID
        payment_id = db.session.execute(
            text("SELECT LAST_INSERT_ID()")
        ).fetchone()[0]
        
        # Create order items
        for item in items:
            db.session.execute(
                text("""
                INSERT INTO order_items (payment_id, product_id, quantity, price)
                VALUES (:payment_id, :product_id, :quantity, :price)
                """),
                {
                    'payment_id': payment_id,
                    'product_id': item[0],
                    'quantity': item[1],
                    'price': item[2]
                }
            )
        
        # Clear the cart
        db.session.execute(
            text("DELETE FROM cart_items WHERE cart_id = :cart_id"),
            {'cart_id': cart[0]}
        )
        db.session.commit()
        
        flash('Payment processed successfully!', 'success')
        return redirect(url_for('payment_success', payment_id=payment_id))
    
    except Exception as e:
        db.session.rollback()
        flash('Payment failed. Please try again.', 'danger')
        return redirect(url_for('checkout'))

@app.route('/payment_success/<int:payment_id>')
@login_required
def payment_success(payment_id):
    # Get payment details
    payment = db.session.execute(
        text("""
        SELECT p.payment_id, p.total_amount, p.payment_date, 
               u.username, u.email
        FROM payments p
        JOIN user u ON p.user_id = u.id
        WHERE p.payment_id = :payment_id
        """),
        {'payment_id': payment_id}
    ).fetchone()

    # Get order items
    items = db.session.execute(
        text("""
        SELECT oi.quantity, oi.price, p.productname, p.image_filename
        FROM order_items oi
        JOIN addagroproducts p ON oi.product_id = p.pid
        WHERE oi.payment_id = :payment_id
        """),
        {'payment_id': payment_id}
    ).fetchall()

    return render_template('payment_success.html', 
                         payment=payment, 
                         items=items)
    
    
@app.route('/my_orders')
@login_required
def my_orders():
    if current_user.role != 'customer':
        abort(403)
    
    # Get orders with their LATEST status
    orders = db.session.execute(
        text("""
        SELECT p.payment_id, p.total_amount, p.payment_date, 
               (SELECT status FROM order_tracking 
                WHERE payment_id = p.payment_id 
                ORDER BY update_time DESC LIMIT 1) AS current_status
        FROM payments p
        WHERE p.user_id = :user_id
        ORDER BY p.payment_date DESC
        """),
        {'user_id': current_user.id}
    ).fetchall()

    return render_template('my_orders.html', orders=orders)

@app.route('/payment_details/<int:payment_id>')
@login_required
def view_payment_details(payment_id):
    if current_user.role != 'customer':
        abort(403)
    
    # Verify the order belongs to the current user
    order = db.session.execute(
        text("SELECT 1 FROM payments WHERE payment_id = :payment_id AND user_id = :user_id"),
        {'payment_id': payment_id, 'user_id': current_user.id}
    ).fetchone()

    if not order:
        abort(404)  # Changed from 403 to 404 for better UX

    # Get order details
    order_info = db.session.execute(
        text("""
        SELECT p.payment_id, p.total_amount, p.payment_date, p.delivery_address,
               p.contact_number, u.username AS seller_name
        FROM payments p
        JOIN order_items oi ON p.payment_id = oi.payment_id
        JOIN addagroproducts ap ON oi.product_id = ap.pid
        JOIN user u ON ap.worker_id = u.id
        WHERE p.payment_id = :payment_id AND p.user_id = :user_id
        LIMIT 1
        """),
        {'payment_id': payment_id, 'user_id': current_user.id}
    ).fetchone()

    # Get all items in the order
    items = db.session.execute(
        text("""
        SELECT oi.quantity, oi.price, ap.productname, ap.image_filename,
               u.username AS seller_name
        FROM order_items oi
        JOIN addagroproducts ap ON oi.product_id = ap.pid
        JOIN user u ON ap.worker_id = u.id
        WHERE oi.payment_id = :payment_id
        """),
        {'payment_id': payment_id}
    ).fetchall()

    # Get tracking history
    tracking = db.session.execute(
        text("""
        SELECT status, update_time, notes
        FROM order_tracking
        WHERE payment_id = :payment_id
        ORDER BY update_time DESC
        """),
        {'payment_id': payment_id}
    ).fetchall()

    return render_template('payment_details.html',
                         order=order_info,
                         items=items,
                         tracking=tracking)


@app.route('/orders_received')
@login_required
def orders_received():
    if current_user.role != 'worker':
        abort(403)
    
    # Get all orders containing this worker's products
    orders = db.session.execute(
        text("""
        SELECT DISTINCT p.payment_id, p.payment_date, p.total_amount, 
               u.username AS customer_name, u.email AS customer_email,
               MAX(t.status) AS current_status
        FROM payments p
        JOIN order_items oi ON p.payment_id = oi.payment_id
        JOIN addagroproducts ap ON oi.product_id = ap.pid
        JOIN user u ON p.user_id = u.id
        LEFT JOIN order_tracking t ON p.payment_id = t.payment_id
        WHERE ap.worker_id = :worker_id
        GROUP BY p.payment_id
        ORDER BY p.payment_date DESC
        """),
        {'worker_id': current_user.id}
    ).fetchall()

    return render_template('orders_received.html', orders=orders)

@app.route('/worker_order_details/<int:payment_id>')
@login_required
def worker_order_details(payment_id):
    if current_user.role != 'worker':
        abort(403)
    
    # Verify the order contains this worker's products
    order_exists = db.session.execute(
        text("""
        SELECT 1 FROM order_items oi
        JOIN addagroproducts ap ON oi.product_id = ap.pid
        WHERE oi.payment_id = :payment_id AND ap.worker_id = :worker_id
        LIMIT 1
        """),
        {'payment_id': payment_id, 'worker_id': current_user.id}
    ).fetchone()

    if not order_exists:
        abort(403)

    # Get order details
    order_info = db.session.execute(
        text("""
        SELECT p.payment_id, p.payment_date, p.total_amount, 
               p.delivery_address, p.contact_number,
               u.username AS customer_name, u.email AS customer_email
        FROM payments p
        JOIN user u ON p.user_id = u.id
        WHERE p.payment_id = :payment_id
        """),
        {'payment_id': payment_id}
    ).fetchone()

    # Get order items (only this worker's products)
    items = db.session.execute(
        text("""
        SELECT oi.quantity, oi.price, ap.productname, ap.image_filename,
               oi.order_item_id
        FROM order_items oi
        JOIN addagroproducts ap ON oi.product_id = ap.pid
        WHERE oi.payment_id = :payment_id AND ap.worker_id = :worker_id
        """),
        {'payment_id': payment_id, 'worker_id': current_user.id}
    ).fetchall()

    # Get tracking history for this order
    tracking = db.session.execute(
        text("""
        SELECT status, update_time, notes
        FROM order_tracking
        WHERE payment_id = :payment_id
        ORDER BY update_time DESC
        """),
        {'payment_id': payment_id}
    ).fetchall()

    # Status options for the form
    status_options = [
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ]

    return render_template('worker_order_details.html',
                         order=order_info,
                         items=items,
                         tracking=tracking,
                         status_options=status_options)

# Payment Status Update (separate endpoint)
@app.route('/update_payment_status/<int:payment_id>', methods=['POST'], endpoint='update_payment_status_view')
@login_required
def update_payment_status(payment_id):
    if current_user.role != 'admin':
        abort(403)
    
    # Your payment status update logic here
    # Example:
    new_status = request.form.get('status')
    db.session.execute(
        text("UPDATE payments SET status = :status WHERE id = :payment_id"),
        {'status': new_status, 'payment_id': payment_id}
    )
    db.session.commit()
    
    flash('Payment status updated', 'success')
    return redirect(url_for('payment_details_view', payment_id=payment_id))


@app.route('/addagroproduct', methods=['POST','GET'])
@login_required
def addagroproduct():
    if request.method == "POST":
        productname = request.form.get('productname')
        productdesc = request.form.get('productdesc')
        price = request.form.get('price')
        
        if not all([productname, productdesc, price]):
            flash('Please fill all required fields', 'danger')
            return redirect(request.url)
        
        try:
            price = float(price)
            if price <= 0:
                flash('Price must be greater than 0', 'danger')
                return redirect(request.url)
        except ValueError:
            flash('Invalid price format', 'danger')
            return redirect(request.url)
        
        if 'productimage' not in request.files:
            flash('No image selected', 'danger')
            return redirect(request.url)
        
        file = request.files['productimage']
        
        if file.filename == '':
            flash('No image selected', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = secure_filename(file.filename)
            unique_filename = f"{current_user.username}_{timestamp}_{original_filename}"
            
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                
                sql = text( """
                    INSERT INTO addagroproducts 
                    (username, email, productname, productdesc, price, image_filename)
                    VALUES (:username, :email, :productname, :productdesc, :price, :image_filename)
                """)
                db.session.execute(sql, {
                    'username': current_user.username,
                    'email': current_user.email,
                    'productname': productname,
                    'productdesc': productdesc,
                    'price': price,
                    'image_filename': unique_filename
                })
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

@app.route('/edit_agro/<int:pid>', methods=['GET', 'POST'])
@login_required
def edit_agro(pid):
    if request.method == 'POST':
        # Using raw SQL
        db.session.execute(text("""
            UPDATE addagroproduct 
            SET productname = :productname, 
                productdesc = :productdesc, 
                price = :price 
            WHERE pid = :pid
        """), {
            'productname': request.form['productname'],
            'productdesc': request.form['productdesc'],
            'price': request.form['price'],
            'pid': pid
        })
        db.session.commit()
        return redirect(url_for('some_route_after_update'))
    
    product = AddAgroProduct.query.get_or_404(pid)
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
