from flask import Flask, render_template, request, redirect, url_for, flash
import api  # Import your existing API client

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Set your secret key

@app.route('/')
def index():
    tasks, error = api.get_tasks()  # Use the existing API client to fetch tasks
    if error:
        flash(f"Error fetching tasks: {error}", 'error')
        tasks = []
    return render_template('index.html', tasks=tasks)

@app.route('/create', methods=['POST'])
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    if not title:
        flash('Title is required!', 'error')
    else:
        _, error = api.create_task(title, description)  # Use the API client to create a task
        if error:
            flash(f"Error creating task: {error}", 'error')
        else:
            flash('Task created successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        _, error = api.update_task(task_id, title, description, status)  # Use the API client to update the task
        if error:
            flash(f"Error updating task: {error}", 'error')
        else:
            flash('Task updated successfully!', 'success')
        return redirect(url_for('index'))

    task, error = api.get_task(task_id)  # Use the API client to fetch the specific task
    if error or task is None:
        flash(f"Error fetching task: {error}", 'error')
        return redirect(url_for('index'))

    return render_template('edit.html', task=task)

@app.route('/delete/<task_id>')
def delete_task(task_id):
    success, error = api.delete_task(task_id)  # Use the API client to delete the task
    if error:
        flash(f"Error deleting task: {error}", 'error')
    else:
        flash('Task deleted successfully!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)