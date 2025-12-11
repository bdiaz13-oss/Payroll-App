# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
import json
import os
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production

# Data handling functions
def load_data():
    if not os.path.exists('data.json'):
        return {"next_id": 1, "employees": []}
    with open('data.json', 'r') as f:
        return json.load(f)

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

# Forms
class EmployeeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    position = StringField('Position', validators=[DataRequired()])
    base_salary = FloatField('Base Salary', validators=[DataRequired(), NumberRange(min=0)])
    tax_rate = FloatField('Tax Rate (e.g., 0.2 for 20%)', validators=[DataRequired(), NumberRange(min=0, max=1)])
    deductions = FloatField('Deductions', validators=[NumberRange(min=0)], default=0)
    submit = SubmitField('Submit')

# Routes
@app.route('/')
def index():
    data = load_data()
    employees = data['employees']
    for emp in employees:
        yearly_net = emp['base_salary'] * (1 - emp['tax_rate']) - emp['deductions']
        emp['net_pay'] = yearly_net / 12  # Calculate monthly net pay
    return render_template('index.html', employees=employees)

@app.route('/add', methods=['GET', 'POST'])
def add():
    form = EmployeeForm()
    if form.validate_on_submit():
        data = load_data()
        emp = {
            "id": data['next_id'],
            "name": form.name.data,
            "position": form.position.data,
            "base_salary": form.base_salary.data,
            "tax_rate": form.tax_rate.data,
            "deductions": form.deductions.data,
            "added_at": datetime.datetime.utcnow().isoformat()
        }
        data['employees'].append(emp)
        data['next_id'] += 1
        save_data(data)
        flash('Employee added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add.html', form=form)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    data = load_data()
    emp = next((e for e in data['employees'] if e['id'] == id), None)
    if not emp:
        return redirect(url_for('index'))
    form = EmployeeForm(
        name=emp['name'],
        position=emp['position'],
        base_salary=emp['base_salary'],
        tax_rate=emp['tax_rate'],
        deductions=emp['deductions']
    )
    if form.validate_on_submit():
        emp['name'] = form.name.data
        emp['position'] = form.position.data
        emp['base_salary'] = form.base_salary.data
        emp['tax_rate'] = form.tax_rate.data
        emp['deductions'] = form.deductions.data
        save_data(data)
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit.html', form=form)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    data = load_data()
    data['employees'] = [e for e in data['employees'] if e['id'] != id]
    save_data(data)
    flash('Employee deleted successfully!', 'danger')
    return redirect(url_for('index'))

@app.route('/payslip/<int:id>')
def payslip(id):
    data = load_data()
    emp = next((e for e in data['employees'] if e['id'] == id), None)
    if not emp:
        return redirect(url_for('index'))
    yearly_net = emp['base_salary'] * (1 - emp['tax_rate']) - emp['deductions']
    net_pay = yearly_net / 12  # Calculate monthly net pay
    return render_template('payslip.html', emp=emp, net_pay=net_pay)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)