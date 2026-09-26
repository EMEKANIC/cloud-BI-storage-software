from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_login import LoginManager, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import pandas as pd
import os
import logging

bcrypt = Bcrypt()
login_manager = LoginManager()

def create_app():
    from app.models import db, Dataset, User
    from app.analytics import build_chart_data
    from app.auth import auth_bp, role_required

    app = Flask(__name__)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(base_dir, '.env'))

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'uploads')
    app.config['PROCESSED_FOLDER'] = os.path.join(base_dir, 'processed')

    logging.basicConfig(
        filename=os.path.join(base_dir, 'app.log'),
        level=logging.WARNING,
        format='%(asctime)s %(levelname)s: %(message)s'
    )

    db_user = os.environ.get('DB_USER')
    db_password = os.environ.get('DB_PASSWORD')
    db_host = os.environ.get('DB_HOST')
    db_name = os.environ.get('DB_NAME')

    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()

    @app.errorhandler(413)
    def file_too_large(e):
        return render_template('upload.html', active='upload',
                                message='File too large. Maximum upload size is 10 MB.', success=False)

    @app.route('/')
    @login_required
    def home():
        datasets = Dataset.query.order_by(Dataset.uploaded_at.desc()).all()
        return render_template('home.html', active='home', datasets=datasets)

    @app.route('/upload', methods=['GET', 'POST'])
    @role_required('analyst', 'admin')
    def upload():
        if request.method == 'POST':
            file = request.files.get('file')
            if not file or file.filename == '':
                return render_template('upload.html', active='upload',
                                        message='Please choose a file to upload.', success=False)

            filename = file.filename
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

            document_extensions = {'doc', 'docx', 'pdf'}

            if ext in document_extensions:
                raw_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(raw_path)

                dataset = Dataset(
                    filename=filename,
                    stored_path=raw_path,
                    row_count=None,
                    column_count=None,
                    missing_values=None,
                    column_names=None,
                    uploaded_by=current_user.id
                )
                db.session.add(dataset)
                db.session.commit()

                return render_template('upload.html', active='upload',
                                        message=f'Uploaded and stored: {filename}', success=True)

            if ext != 'csv':
                return render_template('upload.html', active='upload',
                                        message='Please upload a CSV, Word (.doc/.docx), or PDF file.', success=False)

            raw_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(raw_path)

            try:
                df = pd.read_csv(raw_path)
            except pd.errors.EmptyDataError:
                return render_template('upload.html', active='upload',
                                        message='That file appears to be empty.', success=False)
            except pd.errors.ParserError:
                return render_template('upload.html', active='upload',
                                        message='Could not parse this file. Please check it is a valid CSV.', success=False)
            except Exception as e:
                app.logger.error(f'Upload failed for {file.filename}: {e}')
                return render_template('upload.html', active='upload',
                                        message=f'Could not read file: {e}', success=False)

            if df.empty or len(df.columns) == 0:
                return render_template('upload.html', active='upload',
                                        message='The uploaded file has no usable data.', success=False)

            df.columns = df.columns.str.strip()
            df = df.dropna(how='all')

            processed_path = os.path.join(app.config['PROCESSED_FOLDER'], file.filename)
            df.to_csv(processed_path, index=False)

            dataset = Dataset(
                filename=file.filename,
                stored_path=processed_path,
                row_count=len(df),
                column_count=len(df.columns),
                missing_values=int(df.isnull().sum().sum()),
                column_names=', '.join(df.columns),
                uploaded_by=current_user.id
            )
            db.session.add(dataset)
            db.session.commit()

            summary = {
                'filename': file.filename,
                'rows': dataset.row_count,
                'columns': dataset.column_count,
                'missing_values': dataset.missing_values,
            }
            preview = df.head(10)

            return render_template('upload.html', active='upload',
                                    message=f'Uploaded and saved to database: {file.filename}', success=True,
                                    summary=summary,
                                    table=preview.to_html(classes='data-table', index=False, border=0))

        return render_template('upload.html', active='upload')

    @app.route('/dataset/<int:dataset_id>')
    @login_required
    def view_dataset(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)
        try:
            df = pd.read_csv(dataset.stored_path)
        except Exception:
            return render_template('dataset_detail.html', active='home', dataset=dataset, charts=[])
        charts = build_chart_data(df)
        return render_template('dataset_detail.html', active='home', dataset=dataset, charts=charts)

    @app.route('/dataset/<int:dataset_id>/view')
    @login_required
    def view_file(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)
        if not os.path.exists(dataset.stored_path):
            return "File not found on server.", 404
        return send_file(dataset.stored_path, as_attachment=False)

    @app.route('/dataset/<int:dataset_id>/download')
    @login_required
    def download_file(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)
        if not os.path.exists(dataset.stored_path):
            return "File not found on server.", 404
        return send_file(dataset.stored_path, as_attachment=True, download_name=dataset.filename)

    @app.route('/dataset/<int:dataset_id>/delete', methods=['POST'])
    @role_required('admin')
    def delete_dataset(dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)

        if os.path.exists(dataset.stored_path):
            os.remove(dataset.stored_path)

        raw_path = os.path.join(app.config['UPLOAD_FOLDER'], dataset.filename)
        if os.path.exists(raw_path):
            os.remove(raw_path)

        db.session.delete(dataset)
        db.session.commit()

        return redirect(url_for('home'))

    return app
