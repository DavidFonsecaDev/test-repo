from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple user storage (in production, use database)
users = {
    'admin': {
        'password': 'password',
        'name': 'Admin User',
        'email': 'admin@example.com',
        'is_admin': True
    },
    'user1': {
        'password': 'pass',
        'name': 'John Doe',
        'email': 'john@example.com',
        'is_admin': False
    }
}

# Order storage
orders_file = 'orders.json'
if os.path.exists(orders_file):
    with open(orders_file, 'r') as f:
        orders = json.load(f)
else:
    orders = []

def save_orders():
    with open(orders_file, 'w') as f:
        json.dump(orders, f)

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username
        self.is_admin = users.get(username, {}).get('is_admin', False)

@login_manager.user_loader
def load_user(username):
    if username in users:
        return User(username)
    return None

@app.route('/')
def home():
    return render_template('index.html', paid=session.get('paid', False))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/worker/<worker_name>')
@login_required
def worker_page(worker_name):
    workers = {
        'Alexandre Taborda': {
            'desc': 'Expert sound engineer with over 10 years of experience in mixing and mastering. Specializes in rock and electronic music.',
            'contact': 'john@example.com | Phone: (351) 456-7890',
            'image': 'images/alex.jpg'
        },
        'Joao Silva': {
            'desc': 'Mastering specialist known for her work in classical and jazz genres. Ensures your audio reaches its full potential.',
            'contact': 'jane@example.com | Phone: (351) 456-7891',
            'image': 'https://via.placeholder.com/300x300?text=Worker+2'
        }
    }
    worker = workers.get(worker_name)
    if not worker:
        return 'Worker not found', 404
    return render_template('worker.html', worker_name=worker_name, worker=worker, paid=session.get('paid', False))

@app.route('/upload', methods=['POST'])
def upload_file():
    if not current_user.is_authenticated:
        return 'Please log in first to upload files.'
    
    if 'audio_file' not in request.files:
        return 'No file part'
    file = request.files['audio_file']
    worker = request.form.get('worker', 'unknown')
    if file.filename == '':
        return 'No selected file'
    
    # Check file extension
    if not (file.filename.lower().endswith('.mp3') or file.filename.lower().endswith('.wav')):
        return 'Invalid file type. Only .mp3 and .wav files are allowed.'
    
    # Check MIME type
    allowed_mimes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'audio/x-wav']
    if file.mimetype not in allowed_mimes:
        return f'Invalid file type. Detected MIME type: {file.mimetype}. Only .mp3 and .wav files are allowed.'
    
    # Check file size (e.g., max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    if size > max_size:
        return 'File too large. Maximum size is 50MB.'
    
    filename = f"{worker}_{current_user.username}_{file.filename}"
    try:
        file.save(f"uploads/{filename}")
        
        # Create order
        order = {
            'id': len(orders) + 1,
            'user': current_user.username,
            'user_name': users[current_user.username]['name'],
            'user_email': users[current_user.username]['email'],
            'worker': worker,
            'file': filename,
            'payment_status': 'completed',  # Since PayPal removed, assume completed
            'order_status': 'processing',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'messages': []
        }
        orders.append(order)
        save_orders()
        
        return f'File uploaded successfully! Order #{order["id"]} created for {worker}.'
    except Exception as e:
        return f'Upload failed: {str(e)}'

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin only.')
        return redirect(url_for('home'))
    return render_template('dashboard.html', orders=orders)

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    # Filter orders for current user
    user_orders = [order for order in orders if order.get('user_email') == users[current_user.username]['email']]
    return render_template('user_dashboard.html', user_orders=user_orders)

@app.route('/send_message/<int:order_id>', methods=['POST'])
@login_required
def send_message(order_id):
    message_content = request.form.get('message')
    if not message_content:
        flash('Message cannot be empty.')
        return redirect(url_for('user_dashboard'))
    
    # Find the order
    order = None
    for o in orders:
        if o['id'] == order_id:
            order = o
            break
    
    if not order:
        flash('Order not found.')
        return redirect(url_for('user_dashboard'))
    
    # Check if user owns this order
    if order.get('user_email') != users[current_user.username]['email'] and not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('user_dashboard'))
    
    # Initialize messages list if it doesn't exist
    if 'messages' not in order:
        order['messages'] = []
    
    # Add the message
    message = {
        'sender': current_user.username,
        'sender_name': users[current_user.username]['name'],
        'content': message_content,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    order['messages'].append(message)
    save_orders()
    
    flash('Message sent successfully!')
    return redirect(url_for('user_dashboard'))

@app.route('/update_order/<int:order_id>', methods=['POST'])
@login_required
def update_order(order_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('home'))
    status = request.form.get('status')
    for order in orders:
        if order['id'] == order_id:
            order['order_status'] = status
            save_orders()
            flash(f'Order {order_id} status updated to {status}.')
            break
    return redirect(url_for('dashboard'))

@app.route('/delete_order/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    if not current_user.is_admin:
        flash('Access denied.')
        return redirect(url_for('home'))
    
    global orders
    order_to_delete = None
    for i, order in enumerate(orders):
        if order['id'] == order_id:
            order_to_delete = order
            # Remove the order from the list
            orders.pop(i)
            break
    
    if order_to_delete:
        # Save the updated orders list
        save_orders()
        
        # Optionally delete the uploaded file
        file_path = os.path.join('uploads', order_to_delete['file'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                flash(f'Order {order_id} and associated file deleted successfully.')
            except OSError:
                flash(f'Order {order_id} deleted, but could not delete the file.')
        else:
            flash(f'Order {order_id} deleted successfully.')
    else:
        flash('Order not found.')
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)