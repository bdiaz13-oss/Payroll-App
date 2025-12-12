# app.py (overwrite the entire file with this)
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, FloatField, DateField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange
import json
import os
import datetime
from io import StringIO, BytesIO
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production

# Data handling functions
def load_data():
    if not os.path.exists('data.json'):
        return {"next_employee_id": 1, "next_record_id": 1, "employees": [], "pay_records": []}
    with open('data.json', 'r') as f:
        return json.load(f)

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

# Forms
class EmployeeForm(FlaskForm):
    name = StringField('Employee Name', validators=[DataRequired()])
    pay_rate = FloatField('Hourly Pay Rate', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit')

class PayRecordForm(FlaskForm):
    employee_id = SelectField('Employee', coerce=int, validators=[DataRequired()])
    period_start = DateField('Period Start', validators=[DataRequired()])
    period_end = DateField('Period End', validators=[DataRequired()])
    hours_worked = FloatField('Hours Worked', validators=[DataRequired(), NumberRange(min=0)])
    overtime_hours = FloatField('Overtime Hours', validators=[Optional(), NumberRange(min=0)])
    deductions = FloatField('Deductions', validators=[Optional(), NumberRange(min=0)])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Submit')

class SearchForm(FlaskForm):
    name = StringField('Employee Name')
    period_start = DateField('From Date', validators=[Optional()])
    period_end = DateField('To Date', validators=[Optional()])
    submit = SubmitField('Search')

# Routes
@app.route('/')
def index():
    data = load_data()
    form = SearchForm()
    records = data['pay_records']
    records = sorted(records, key=lambda x: x['period_start'], reverse=True)

    # Apply filters
    name = request.args.get('name')
    start = request.args.get('period_start')
    end = request.args.get('period_end')
    if name:
        records = [r for r in records if get_employee_name(data, r['employee_id']).lower().find(name.lower()) >= 0]
    if start:
        start_date = datetime.date.fromisoformat(start)
        records = [r for r in records if datetime.date.fromisoformat(r['period_start']) >= start_date]
    if end:
        end_date = datetime.date.fromisoformat(end)
        records = [r for r in records if datetime.date.fromisoformat(r['period_end']) <= end_date]

    page = request.args.get('page', 1, type=int)
    per_page = 6
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_records = records[start_idx:end_idx]
    has_more = end_idx < len(records)

    enriched_records = []
    for r in paginated_records:
        r_copy = r.copy()
        r_copy['employee_name'] = get_employee_name(data, r['employee_id'])
        enriched_records.append(r_copy)

    return render_template('index.html', records=enriched_records, form=form, page=page, has_more=has_more, name=name, period_start=start, period_end=end)

def get_employee_name(data, employee_id):
    emp = next((e for e in data['employees'] if e['id'] == employee_id), None)
    return emp['name'] if emp else 'Unknown'

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    form = EmployeeForm()
    if form.validate_on_submit():
        data = load_data()
        emp = {
            "id": data['next_employee_id'],
            "name": form.name.data,
            "pay_rate": form.pay_rate.data
        }
        data['employees'].append(emp)
        data['next_employee_id'] += 1
        save_data(data)
        flash('Employee added successfully!', 'success')
        return redirect(url_for('employees'))
    return render_template('add_employee.html', form=form)

@app.route('/employees')
def employees():
    data = load_data()
    return render_template('employees.html', employees=data['employees'])

@app.route('/edit_employee/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    data = load_data()
    emp = next((e for e in data['employees'] if e['id'] == id), None)
    if not emp:
        return redirect(url_for('employees'))
    form = EmployeeForm(name=emp['name'], pay_rate=emp['pay_rate'])
    if form.validate_on_submit():
        emp['name'] = form.name.data
        emp['pay_rate'] = form.pay_rate.data
        save_data(data)
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('employees'))
    return render_template('edit_employee.html', form=form)

@app.route('/delete_employee/<int:id>', methods=['POST'])
def delete_employee(id):
    data = load_data()
    data['employees'] = [e for e in data['employees'] if e['id'] != id]
    # Also remove related records? For now, keep but handle unknown
    save_data(data)
    flash('Employee deleted successfully!', 'danger')
    return redirect(url_for('employees'))

@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    data = load_data()
    form = PayRecordForm()
    form.employee_id.choices = [(e['id'], e['name']) for e in data['employees']]
    if form.validate_on_submit():
        emp = next(e for e in data['employees'] if e['id'] == form.employee_id.data)
        gross_pay = (form.hours_worked.data * emp['pay_rate']) + (form.overtime_hours.data * emp['pay_rate'] * 1.5)
        deductions = form.deductions.data or 0
        net_pay = gross_pay - deductions
        rec = {
            "id": data['next_record_id'],
            "employee_id": form.employee_id.data,
            "period_start": form.period_start.data.isoformat(),
            "period_end": form.period_end.data.isoformat(),
            "hours_worked": form.hours_worked.data,
            "overtime_hours": form.overtime_hours.data or 0,
            "deductions": deductions,
            "notes": form.notes.data,
            "gross_pay": gross_pay,
            "net_pay": net_pay,
            "added_at": datetime.datetime.utcnow().isoformat()
        }
        data['pay_records'].append(rec)
        data['next_record_id'] += 1
        save_data(data)
        flash('Pay record added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_record.html', form=form)

@app.route('/edit_record/<int:id>', methods=['GET', 'POST'])
def edit_record(id):
    data = load_data()
    rec = next((r for r in data['pay_records'] if r['id'] == id), None)
    if not rec:
        return redirect(url_for('index'))
    form = PayRecordForm(
        employee_id=rec['employee_id'],
        period_start=datetime.date.fromisoformat(rec['period_start']),
        period_end=datetime.date.fromisoformat(rec['period_end']),
        hours_worked=rec['hours_worked'],
        overtime_hours=rec['overtime_hours'],
        deductions=rec['deductions'],
        notes=rec['notes']
    )
    form.employee_id.choices = [(e['id'], e['name']) for e in data['employees']]
    if form.validate_on_submit():
        emp = next(e for e in data['employees'] if e['id'] == form.employee_id.data)
        gross_pay = (form.hours_worked.data * emp['pay_rate']) + (form.overtime_hours.data * emp['pay_rate'] * 1.5)
        deductions = form.deductions.data or 0
        net_pay = gross_pay - deductions
        rec['employee_id'] = form.employee_id.data
        rec['period_start'] = form.period_start.data.isoformat()
        rec['period_end'] = form.period_end.data.isoformat()
        rec['hours_worked'] = form.hours_worked.data
        rec['overtime_hours'] = form.overtime_hours.data or 0
        rec['deductions'] = deductions
        rec['notes'] = form.notes.data
        rec['gross_pay'] = gross_pay
        rec['net_pay'] = net_pay
        save_data(data)
        flash('Pay record updated successfully!', 'success')
        return redirect(url_for('view_record', id=id))
    return render_template('edit_record.html', form=form)

@app.route('/record/<int:id>')
def view_record(id):
    data = load_data()
    rec = next((r for r in data['pay_records'] if r['id'] == id), None)
    if not rec:
        return redirect(url_for('index'))
    rec['employee_name'] = get_employee_name(data, rec['employee_id'])
    return render_template('record.html', rec=rec)

@app.route('/delete_record/<int:id>', methods=['POST'])
def delete_record(id):
    data = load_data()
    data['pay_records'] = [r for r in data['pay_records'] if r['id'] != id]
    save_data(data)
    flash('Pay record deleted successfully!', 'danger')
    return redirect(url_for('index'))

@app.route('/export_csv')
def export_csv():
    data = load_data()
    records = data['pay_records']
    # Enrich with names
    for r in records:
        r['employee_name'] = get_employee_name(data, r['employee_id'])

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Employee Name', 'Period Start', 'Period End', 'Hours Worked', 'Overtime Hours', 'Gross Pay', 'Deductions', 'Net Pay', 'Notes'])
    for r in records:
        cw.writerow([r['id'], r['employee_name'], r['period_start'], r['period_end'], r['hours_worked'], r['overtime_hours'], r['gross_pay'], r['deductions'], r['net_pay'], r['notes']])
    output = si.getvalue()
    si.close()

    return send_file(BytesIO(output.encode()), mimetype='text/csv', as_attachment=True, download_name='pay_records.csv')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)