from flask import Blueprint, request, redirect, url_for, render_template, flash, current_app,session
from flask_login import login_user, logout_user, login_required
from models import User, Broker  # Using raw-SQL models
from werkzeug.security import generate_password_hash

auth = Blueprint("auth", __name__)

# List of admin usernames (you can hardcode these or use other criteria)
ADMIN_USERS = {
    "admin1": "password1",
    "admin2": "password2",
    # Add more admins here
}

@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name")
        password = request.form.get("password")
        
        # Admin login
        if name in current_app.config['ADMIN_USERS']:
            if current_app.config['ADMIN_USERS'][name] == password:
                admin_user = User(
                    user_id=0,  # Special admin ID
                    name=name,
                    password_hash=generate_password_hash(password),
                    brokerage_id=None,
                    balance=0,
                    is_admin=True  # Explicitly mark as admin
                )
                login_user(admin_user)
                session['admin_name'] = name  # Store in session
                print(f"Admin {name} authenticated successfully")
                return redirect(url_for('admin.admin_dashboard'))
        
        # Regular user login
        user = User.fetch_user_by_name(name)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('portfolio.view_portfolio'))
        
        flash("Invalid credentials")
        return redirect(url_for('auth.login'))
    
    return render_template('login.html')

@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        brokerage_id = request.form.get("brokerage")
        balance = request.form.get("balance")

        if not brokerage_id:
            flash("Please select a brokerage.")
            return redirect(url_for("auth.signup"))
        
        if not balance or int(balance) < 1000:
            flash("Minimum starting balance is 1000.")
            return redirect(url_for("auth.signup"))

        brokers = Broker.fetch_all_brokers()
        valid_ids = [broker.brokerage_id for broker in brokers]

        if int(brokerage_id) not in valid_ids:
            flash("Invalid brokerage selected.")
            return redirect(url_for("auth.signup"))

        existing_user = User.fetch_user_by_name(name)
        if existing_user:
            flash("Username already taken, try another one.", "error")
            return render_template("signup.html", brokers=brokers)

        # Create user
        User.create_user(name, password, brokerage_id, int(balance))

        # 🔥 **Update the broker's user count**
        Broker.update_user_count(brokerage_id)

        flash("Account created! You can now log in.")
        return redirect(url_for("auth.login"))
    
    brokers = Broker.fetch_all_brokers()
    return render_template("signup.html", brokers=brokers)


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

