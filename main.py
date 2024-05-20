from flask import Flask, render_template, request, redirect, session, flash
from flask_paginate import Pagination, get_page_parameter
from werkzeug.security import generate_password_hash, check_password_hash
import pymongo
import os
import re
from time import strftime

SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key')

app = Flask(__name__)
app.secret_key = SECRET_KEY

# MongoDB'ye bağlantı kur
client = pymongo.MongoClient()
db = client["ToDoDB"]

def get_next_sequence_value(seq_name):
    sequence_document = db.counters.find_one_and_update(
        filter={"_id": seq_name},
        update={"$inc": {"seq": 1}},
        upsert=True
    )
    if sequence_document is None:
        raise ValueError("Sequence belgesi bulunamadı.")
    return sequence_document["seq"]

def check_password_format(password):
    # Şifrenin en az 8 karakterden oluştuğunu, en az bir büyük harf, bir küçük harf ve bir rakam içerdiğini kontrol et
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    return True

@app.route('/')
def ana_sayfa():
    return render_template("ana_sayfa.html")

@app.route('/home', methods=["GET"])
def home_page():
    if 'kullanici' in session:
        kullanici_email = session['kullanici']['_id']
        page = request.args.get(get_page_parameter(), type=int, default=1)
        per_page = 6  # Sayfa başına gösterilecek görev sayısı

        gorevler = list(db["gorevler"].find({"kullanici_email": kullanici_email}).sort("_id", -1))
        total = len(gorevler)

        pagination = Pagination(page=page, per_page=per_page, total=total)

        gorevler = gorevler[(page - 1) * per_page: page * per_page]

        tamamlanan_gorev_sayisi = sum(1 for gorev in gorevler if gorev["tamamlandi"])
        toplam_gorev_sayisi = len(gorevler)

        if toplam_gorev_sayisi == 0:
            ilerleme_yuzdesi = 0
        else:
            ilerleme_yuzdesi = (tamamlanan_gorev_sayisi / toplam_gorev_sayisi) * 100

        if not gorevler:
            return render_template("gorev.html", aktif_gorev=None, gorevler=[], yapilacaklar=[], ilerleme_yuzdesi=ilerleme_yuzdesi, pagination=pagination)
        aktif_gorev = gorevler[0]
        yapilacaklar = list(db["gorevler"].find({"gorev_id": aktif_gorev["_id"], "kullanici_email": kullanici_email}))
        return render_template("gorev.html", aktif_gorev=aktif_gorev, gorevler=gorevler, yapilacaklar=yapilacaklar, ilerleme_yuzdesi=ilerleme_yuzdesi, pagination=pagination)
    else:
        return redirect("/giris", 302)

@app.route('/gorev-ekle', methods=["GET", "POST"])
def gorev_ekle():
    if request.method == 'GET':
        return render_template("gorev.html")
    elif request.method == 'POST':
        gorev = request.form["gorev"]
        tarih = strftime(" %X %d %B, %Y")  # Mevcut zamanı al
        kullanici_email = session['kullanici']['_id']
        db["gorevler"].insert_one({
            "_id": get_next_sequence_value("gorevler"),
            "gorev": gorev,
            "tarih": tarih,
            "tamamlandi": False,
            "kullanici_email": kullanici_email
        })
        return redirect("/home", 302)

@app.route('/gorev/<gorev_id>')
def gorev_goster(gorev_id):
    if request.method == 'GET':
        kullanici_email = session['kullanici']['_id']
        gorevler = list(db["gorevler"].find({"kullanici_email": kullanici_email}).sort("_id", -1))
        aktif_gorev = db["gorevler"].find_one({"_id": int(gorev_id), "kullanici_email": kullanici_email})
        yapilacaklar = list(db["yapilacaklar"].find({"gorev_id": int(gorev_id), "kullanici_email": kullanici_email}))
        return render_template("gorev.html", aktif_gorev=aktif_gorev, gorevler=gorevler, yapilacaklar=yapilacaklar)

@app.route('/gorev-sil/<gorev_id>', methods=["POST"])
def gorev_sil(gorev_id):
    kullanici_email = session['kullanici']['_id']
    db["gorevler"].delete_one({"_id": int(gorev_id), "kullanici_email": kullanici_email})
    return redirect("/home", 302)


@app.route('/gorev-tamamla/<gorev_id>', methods=["POST"])
def gorev_tamamla(gorev_id):
    kullanici_email = session['kullanici']['_id']

    # Görevin tamamlandığı zamanı al
    tamamlanma_zamani = strftime(" %X %d %B, %Y")

    # Görevin tamamlandı bayrağını ve tamamlanma zamanını güncelle
    db["gorevler"].update_one(
        {"_id": int(gorev_id), "kullanici_email": kullanici_email},
        {"$set": {"tamamlandi": True, "tamamlanma_zamani": tamamlanma_zamani}}
    )

    return redirect("/home", 302)

@app.route('/uye-ol', methods=["GET", "POST"])
def uye_ol():
    if request.method == 'GET':
        return render_template("gorev.html")
    else:
        # Formdan gelen verileri al
        email = request.form["email"]
        sifre = request.form["sifre"]
        adsoyad = request.form["adsoyad"]

        # Öncelikle veritabanında bu e-posta adresiyle kullanıcı olup olmadığını kontrol et
        existing_user = db["kullanicilar"].find_one({"_id": email})
        if existing_user:
            flash("Bu e-posta adresi zaten kullanılıyor. Lütfen başka bir e-posta adresi deneyin.", "error")
            return redirect("/", 302)

        # Şifre formatını kontrol et
        if not check_password_format(sifre):
            flash("Şifre formatı geçersiz. En az 8 karakterden oluşmalı, en az bir büyük harf, bir küçük harf ve bir rakam içermelidir.", "error")
            return redirect("/", 302)

        # Şifreyi hash'le
        sifre_hash = generate_password_hash(sifre)

        # Veritabanına kullanıcıyı ekle
        db["kullanicilar"].insert_one({
            "_id": email,
            "sifre": sifre_hash,
            "adsoyad": adsoyad
        })

        # Oturum başlat
        kullanici = db["kullanicilar"].find_one({"_id": email})
        session['kullanici'] = kullanici
        return redirect("/home", 302)
@app.route('/giris', methods=["GET", "POST"])
def giris():
    if request.method == 'GET':
        return render_template("gorev.html")
    else:
        # Formdan gelen verileri al
        email = request.form["email"]
        girilen_sifre = request.form["sifre"]

        kullanici = db["kullanicilar"].find_one({"_id": email})

        if kullanici and check_password_hash(kullanici["sifre"], girilen_sifre):
            session['kullanici'] = kullanici
            return redirect("/home", 302)
        else:
            flash("Kullanıcı bulunamadı ya da şifre geçersiz", "error")
            return redirect("/", 302)

@app.route('/cikis', methods=["GET", "POST"])
def cikis():
    session.pop('kullanici', None)
    return redirect("/", 302)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
