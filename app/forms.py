from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    IntegerField,
    BooleanField,
    SelectField,
)
from wtforms.validators import DataRequired, Length, Optional


class LoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    submit = SubmitField("Ingresar")


class UserForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(max=80)])
    nombre = StringField("Nombre", validators=[Length(max=120)])
    apellido = StringField("Apellido", validators=[Length(max=120)])
    role = SelectField(
        "Rol",
        choices=[("admin", "Administrador"), ("helper", "Ayudante"), ("viewer", "Solo vista")],
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Contraseña", validators=[Optional(), Length(min=4, max=255)]
    )
    submit = SubmitField("Guardar")


class PersonForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=120)])
    apellido = StringField("Apellido", validators=[Length(max=120)])
    cedula = StringField("Cédula", validators=[Length(max=30)])
    telefono = StringField("Teléfono", validators=[Length(max=80)])
    edad = IntegerField("Edad")
    tiene_familiar = BooleanField("Tiene familiar")
    submit = SubmitField("Guardar")
