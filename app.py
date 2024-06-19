import os
from os.path import join, dirname
from dotenv import load_dotenv

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash

from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
from werkzeug.utils import secure_filename

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")


client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret_key_here"
app.config["UPLOAD_FOLDER"] = "static"
app.config['SESSION_PERMANENT'] = False

# Route untuk halaman home
@app.route('/')
def home():
    return render_template('home.html')

# Route untuk halaman aboutus
@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

# Route untuk halaman products
@app.route('/products')
def products():
    return render_template('products.html')

# Route untuk halaman FAQ
@app.route('/faq')
def faq():
    return render_template('faq.html')

def is_admin():
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    return session.get('username') == admin_username and session.get('password') == admin_password


# Route untuk halaman contact
@app.route('/contact')
def contact():
    return render_template('contact.html')

# Route untuk halaman ulasan
@app.route('/ulasan')
def ulasan():
    return redirect(url_for('ulas'))
    #return render_template('ulasan.html')


@app.route('/ulas')
def ulas():
    if 'username' not in session:  
        return redirect(url_for('login'))  
    articles = list(db.collection.find({}))  # db adalah objek koneksi ke database MongoDB
    return render_template('ulasan.html', articles=articles)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Periksa apakah pengguna adalah admin
        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if username == admin_username and password == admin_password:
            session['username'] = username
            session['password'] = password
            session.permanent = False
            return redirect(url_for('ulasan'))
        else:
            user = db.users.find_one({"username": username, "password": password})
            if user:
                session['username'] = username
                session['password'] = password
                session.permanent = False
                return redirect(url_for('ulasan'))
            else:
                error = "Username atau Password salah!"
    return render_template('login.html', error=error)




# Add the logout route
@app.route('/logout')
def logout():
    # Remove the 'username' session variable to signify user logout
    session.pop('username', None)
    # Redirect user to the home page after logout
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None  # Inisialisasi variabel error
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if db.users.find_one({"username": username}):
            error = "Username sudah ada!"
        else:
            db.users.insert_one({"username": username, "password": password})
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/rate', methods=['GET'])
def show_rate():
    articles = list(db.rate.find({}, {'_id': True, 'title': True, 'content': True, 'star': True, 'file': True, 'time': True}))
    # Mengirimkan _id sebagai bagian dari respons
    articles = [{**article, '_id': str(article['_id'])} for article in articles]  # Konversi ObjectId ke string
    return jsonify({'articles': articles})

@app.route('/rate', methods=['POST'])
def save_rate():
    title_receive = request.form.get("title_give")
    content_receive = request.form.get("content_give")
    star_receive = request.form.get('star_give')
    username = session.get('username')

    if not title_receive or not content_receive or not star_receive:
        return jsonify({'msg': 'Ada field yang belum diisi'}), 400

    try:
        star_receive = int(star_receive)
    except ValueError:
        return jsonify({'msg': 'Rating tidak valid'}), 400

    file = request.files.get("file_give")

    if not file:
        return jsonify({'msg': 'File belum diupload'}), 400

    extension = file.filename.split('.')[-1]
    today = datetime.now()
    mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
    filename = f'file-{mytime}.{extension}'
    save_to = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(save_to)

    time = today.strftime('%Y-%m-%d')

    doc = {
        'file': filename,
        'title': title_receive,
        'star': star_receive,
        'content': content_receive,
        'time': time,
        'username': username  # Tambahkan informasi username ke dalam dokumen
    }
    db.rate.insert_one(doc)
    return jsonify({'msg': 'Upload selesai!'}), 200


@app.route('/delete/<id>', methods=['POST'])
def delete_rate(id):
    try:
        print(f"ID yang diterima: {id}")  # Log untuk memeriksa ID yang diterima
        
        # Dapatkan ulasan dari database
        article = db.rate.find_one({"_id": ObjectId(id)})
        
        if not article:
            return jsonify({'msg': 'Ulasan tidak ditemukan!'}), 404

        # Hanya admin atau pemilik ulasan yang dapat menghapus ulasan
        if not is_admin() and session.get('username') != article.get('username'):
            return jsonify({'msg': 'Anda tidak memiliki izin untuk menghapus ulasan ini! Hanya admin dan pembuat ulasan yang dapat menghapus ulasan ini'}), 403

        # Menghapus dokumen dari database
        db.rate.delete_one({"_id": ObjectId(id)})  # Gunakan ObjectId untuk mengubah string menjadi ObjectId
        
        # Menghapus gambar terkait dari direktori static
        if article and 'file' in article:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], article['file'])
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"File {article['file']} telah dihapus dari direktori static.")  # Tambahkan pesan log
        
        print(f"Ulasan dengan ID {id} telah dihapus dari database.")  # Tambahkan pesan log
        
        return jsonify({'msg': 'Hapus ulasan berhasil!'}), 200
    except Exception as e:
        print(e)
        return jsonify({'msg': 'Gagal menghapus ulasan!'}), 500



@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit_rate(id):
    if request.method == 'POST':
        title_receive = request.form.get("title")
        content_receive = request.form.get("content")
        star_receive = request.form.get('star')
        ulasan_id = request.form.get('id')  # Mengambil id dari form

        if not title_receive or not content_receive or not star_receive:
            flash('Ada field yang belum diisi', 'error')
            return redirect(url_for('edit_rate', id=ulasan_id))

        try:
            star_receive = int(star_receive)
        except ValueError:
            flash('Rating tidak valid', 'error')
            return redirect(url_for('edit_rate', id=ulasan_id))

        # Dapatkan ulasan dari database
        article = db.rate.find_one({"_id": ObjectId(ulasan_id)})

        if not article:
            flash('Ulasan tidak ditemukan!', 'error')
            return redirect(url_for('edit_rate', id=ulasan_id))

        # Hanya admin atau pemilik ulasan yang dapat mengedit ulasan
        if not is_admin() and session.get('username') != article.get('username'):
            flash('Anda tidak memiliki izin untuk mengedit ulasan ini!, Hanya admin dan pembuat ulasan yang dapat mengedit ulasan ini', 'error')
            return redirect(url_for('edit_rate', id=ulasan_id))

        doc = {
            'title': title_receive,
            'star': star_receive,
            'content': content_receive,
        }

        file = request.files.get("file")
        if file:
            extension = file.filename.split('.')[-1]
            today = datetime.now()
            mytime = today.strftime('%Y-%m-%d-%H-%M-%S')
            filename = f'file-{mytime}.{extension}'
            save_to = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(save_to)
            doc['file'] = filename

        db.rate.update_one({"_id": ObjectId(ulasan_id)}, {"$set": doc})  # Konversi ulasan_id ke ObjectId
        flash('Ulasan berhasil diubah', 'success')
        return redirect(url_for('ulasan'))  # Arahkan pengguna ke halaman ulasan setelah berhasil diubah

    article = db.rate.find_one({"_id": ObjectId(id)})  # Konversi id ke ObjectId

    # Hanya admin atau pemilik ulasan yang dapat mengedit ulasan
    if not is_admin() and session.get('username') != article.get('username'):
        flash('Anda tidak memiliki izin untuk mengedit ulasan ini!,Hanya admin dan pembuat ulasan yang dapat mengedit ulasan ini', 'error')
        return redirect(url_for('ulasan'))

    return render_template('edit.html', article=article)

@app.route('/edit_permission/<id>', methods=['GET'])
def edit_permission(id):
    article = db.rate.find_one({"_id": ObjectId(id)})
    if not article:
        return jsonify({'allowed': False})
    if is_admin() or session.get('username') == article.get('username'):
        return jsonify({'allowed': True})
    return jsonify({'allowed': False})


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)
