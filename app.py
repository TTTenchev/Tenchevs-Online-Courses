import logging
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.logging.configuration.api_logging_configuration import (
    LoggingConfiguration,
    RequestLoggingConfiguration,
    ResponseLoggingConfiguration,
)
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.controllers.orders_controller import OrdersController
from paypalserversdk.controllers.payments_controller import PaymentsController
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.capture_request import CaptureRequest
from paypalserversdk.models.money import Money
from paypalserversdk.models.shipping_details import ShippingDetails
from paypalserversdk.models.shipping_option import ShippingOption
from paypalserversdk.models.shipping_type import ShippingType
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.models.payment_source import PaymentSource
from paypalserversdk.models.card_request import CardRequest
from paypalserversdk.models.card_attributes import CardAttributes
from paypalserversdk.models.card_verification import CardVerification
from paypalserversdk.models.card_verification_method import CardVerificationMethod
from paypalserversdk.api_helper import ApiHelper
import random

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
db = SQLAlchemy(app)
admin = Admin(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

BACKGROUND_CLASSES = ["image-1", "image-2", "image-3"]

SPECIALTIES = [
    "Software Developer",
    "Data Scientist",
    "Cybersecurity Specialist",
    "Network Engineer",
    "DevOps Engineer",
    "Cloud Architect",
    "Database Administrator",
    "Web Developer",
    "Mobile Application Developer",
    "IT Support Specialist",
    "Machine Learning Engineer",
    "Game Developer",
    "System Administrator",
    "IT Project Manager",
    "Blockchain Developer",
    "Artificial Intelligence Engineer",
    "Business Analyst",
    "Quality Assurance Engineer",
    "UI/UX Designer",
    "IT Consultant",
]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    teacher_number = db.Column(db.String(20))
    specialty = db.Column(db.String(50))


class Payments(db.Model):
    email_address = db.Column(db.Integer, nullable=False)
    account_id = db.Column(db.String, db.ForeignKey("user.id"), nullable=False)
    value = db.Column(db.Numeric, nullable=False)
    id = db.Column(db.String, primary_key=True, unique=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    user = db.relationship("User", backref="payments", lazy=True)
    course = db.relationship("Courses", backref="payments", lazy=True)


class Courses(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, unique=True)
    name = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    users_in = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)


class UserCourses(db.Model):
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id"), primary_key=True, nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True, nullable=False
    )

    user = db.relationship("User", backref=db.backref("user_courses", lazy=True))
    course = db.relationship("Courses", backref=db.backref("user_courses", lazy=True))


class UserModelView(ModelView):
    column_display_pk = True
    form_columns = [
        "nickname",
        "username",
        "password",
        "role",
        "teacher_number",
        "specialty",
    ]


paypal_client: PaypalServersdkClient = PaypalServersdkClient(
    client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
        o_auth_client_id="Aa5aUMWaMlLgV--VKm1c6YpyLGmlCrSoHNQRjtZeeqz9h7drKOYve6YYAvhYFL4j2_NZbpXklEUhNQdg",
        o_auth_client_secret="EFAnthcwpaMQMJcD7JUKszCSzMtk5iTLbslpsP7m_39fnPpSq_HUxSGibmS_RHKDP8yK2_SDX94Q0LAF",
    ),
    logging_configuration=LoggingConfiguration(
        log_level=logging.INFO,
        # Disable masking of sensitive headers for Sandbox testing.
        # This should be set to True (the default if unset)in production.
        mask_sensitive_headers=True,
        request_logging_config=RequestLoggingConfiguration(
            log_headers=True, log_body=True
        ),
        response_logging_config=ResponseLoggingConfiguration(
            log_headers=True, log_body=True
        ),
    ),
)

orders_controller: OrdersController = paypal_client.orders
payments_controller: PaymentsController = paypal_client.payments


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class AdminView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == "admin"

    def inaccessible_callback(self, name, **kwargs):
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("login"))


class UserAdminView(AdminView):
    column_list = ("id", "nickname", "username", "role", "teacher_number", "specialty")
    column_labels = {
        "nickname": "Nickname",
        "username": "Username",
        "role": "Role",
        "teacher_number": "Teacher Number",
        "specialty": "Specialty",
    }


class PaymentsAdminView(AdminView):
    column_list = ("id", "account_id", "course_id", "value", "email_address")
    column_labels = {
        "account_id": "Account ID",
        "course_id": "Course ID",
        "value": "Payment Value",
        "email_address": "Email Address",
    }
    column_formatters = {
        "account_id": lambda v, c, m, p: (m.user.nickname if m.user else "N/A"),
        "course_id": lambda v, c, m, p: (m.course.name if m.course else "N/A"),
    }


class CoursesAdminView(AdminView):
    column_list = ("id", "name", "price", "description", "content")
    column_labels = {
        "name": "Course Name",
        "price": "Price",
        "description": "Description",
        "content": "Course Content",
    }


class UserCourseView(AdminView):
    column_list = {"user_id", "course_id"}
    column_labels = {
        "user_id": "User ID",
        "course_id": "Course ID",
    }
    column_formatters = {
        "user_id": lambda v, c, m, p: (m.user.nickname if m.user else "N/A"),
        "course_id": lambda v, c, m, p: (m.course.name if m.course else "N/A"),
    }


admin.add_view(UserAdminView(User, db.session))
admin.add_view(PaymentsAdminView(Payments, db.session))
admin.add_view(CoursesAdminView(Courses, db.session))
admin.add_view(UserCourseView(UserCourses, db.session))


def load_courses():
    courses = Courses.query.all()
    return courses



random_background_class = random.choice(BACKGROUND_CLASSES)



@app.route("/")
def landing_page():
    return render_template("landing.html", background_class=random_background_class)


@app.route("/dashboard")
@login_required
def dashboard():
    courses = load_courses()
    if(current_user.role == 'student'):
        isStudent = True
    else:
        isStudent = False
    return render_template(
        "dashboard.html", courses=courses, background_class=random_background_class, isStudent = isStudent,
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Username and password do not match any existing account!", "error")
            return render_template(
                "login.html", background_class=random_background_class
            )
    return render_template("login.html", background_class=random_background_class)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out!", "info")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nickname = request.form["nickname"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form["role"]
        teacher_number = request.form["teacher_number"]
        specialty = request.form["specialty"]
        if password == confirm_password:
            if not teacher_number:
                specialty = None
            new_user = User(
                nickname=nickname,
                username=username,
                password=password,
                role=role,
                teacher_number=teacher_number if teacher_number else None,
                specialty=specialty,
            )
            try:
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for("login"))
            except:
                db.session.rollback()
                flash(f"Username {new_user.nickname} already exists.", "error")
                return render_template(
                    "register.html",
                    specialties=SPECIALTIES,
                    background_class=random_background_class,
                )

    return render_template(
        "register.html",
        specialties=SPECIALTIES,
        background_class=random_background_class,
    )


@app.route("/api/orders", methods=["POST"])
@login_required
def create_order():
    request_body = request.get_json()
    cart = request_body["cart"]
    order = orders_controller.orders_create(
        {
            "body": OrderRequest(
                intent=CheckoutPaymentIntent.CAPTURE,
                purchase_units=[
                    PurchaseUnitRequest(
                        amount=AmountWithBreakdown(
                            currency_code="USD",
                            value=cart[0].get("price"),
                        ),
                        description="Course Purchase",
                        custom_id=cart[0].get("course_id"),
                    )
                ],
            )
        }
    )
    return ApiHelper.json_serialize(order.body)


@app.route("/create_course", methods=["GET", "POST"])
@login_required
def create_course():
    if current_user.role == "student":
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form["course_name"]
        price = request.form["price"]
        description = request.form["description"]
        content = request.form["content"]
        new_course = Courses(
            name=name,
            price=price,
            description=description,
            content=content,
            users_in=None,
        )
        try:
            db.session.add(new_course)
            db.session.commit()
            flash("Course was added", "success")
            return redirect(url_for("dashboard"))
        except:
            db.session.rollback()
            flash("Course was not added", "info")
            return render_template("create_course.html", user_id=current_user.id)
    return render_template("create_course.html", user_id=current_user.id)


@app.route("/course/")
@login_required
def course():
    course_id = request.args.get("course_id")
    course_info = Courses.query.get(course_id)
    user_course = UserCourses.query.filter_by(
        user_id=current_user.id, course_id=course_id
    ).first()
    if user_course:
        course_info.shown = True
    else:
        course_info.shown = False
    return render_template("course.html", course=course_info)


@app.route("/payment")
@login_required
def payment():
    price = request.args.get("price")
    course_id = request.args.get("course_id")
    return render_template("payment.html", price=price, course_id=course_id, background_class= random_background_class)

@app.route("/my_profile")
@login_required
def my_profile():
    user_courses = UserCourses.query.filter_by(user_id=current_user.id).all()
    course_ids = [uc.course_id for uc in user_courses]
    courses = Courses.query.filter(Courses.id.in_(course_ids)).all()
    return render_template("my_profile.html", user = current_user, courses = courses, background_class = random_background_class)


@app.route("/api/orders/<order_id>/capture", methods=["POST"])
@login_required
def capture_order(order_id):
    order = orders_controller.orders_capture(
        {"id": order_id, "prefer": "return=representation"}
    )
    current_order = json.loads(ApiHelper.json_serialize(order))
    email_address = (
        current_order.get("body", {})
        .get("payment_source", {})
        .get("paypal", {})
        .get("email_address")
    )
    course_id = (
        current_order.get("body", {}).get("purchase_units", [{}])[0].get("custom_id")
    )
    value = (
        current_order.get("body", {})
        .get("purchase_units", [{}])[0]
        .get("amount", {})
        .get("value")
    )
    new_order = Payments(
        email_address=email_address,
        account_id=current_user.id,
        value=value,
        id=order_id,
        course_id=course_id,
    )
    db.session.add(new_order)
    db.session.commit()
    user_course = UserCourses(course_id=course_id, user_id=current_user.id)
    db.session.add(user_course)
    db.session.commit()

    return ApiHelper.json_serialize(order)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
