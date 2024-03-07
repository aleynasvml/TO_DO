from flask import Flask, render_template, request, redirect, session
import pymongo

app = Flask(__name__)
app.secret_key = 'cok gizli super secret key'

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
@app.route('/')
def home_page():
    gorevler = list(db["gorevler"].find().sort("_id", -1))
    if not gorevler:
        return render_template("gorev.html", aktif_gorev=None, gorevler=[], yapilacaklar=[])

    aktif_gorev = gorevler[0]
    yapilacaklar = list(db["yapilacaklar"].find({"gorev_id": aktif_gorev["_id"]}))
    return render_template("gorev.html", aktif_gorev=aktif_gorev, gorevler=gorevler, yapilacaklar=yapilacaklar)


@app.route('/gorev-ekle', methods=["GET", "POST"])
def gorev_ekle():
    if request.method == 'GET':
        return render_template("gorev_ekle.html")
    elif request.method == 'POST':
        gorev = request.form["gorev"]
        db["gorevler"].insert_one({
            "_id": get_next_sequence_value("gorevler"),
            "gorev": gorev
        })
        return redirect("/", 302)

@app.route('/gorev/<gorev_id>')
def gorev_goster(gorev_id):
    if request.method == 'GET':
        gorevler = list(db["gorevler"].find().sort("_id", -1))
        aktif_gorev = db["gorevler"].find_one({"_id": int(gorev_id)})
        yapilacaklar = list(db["yapilacaklar"].find({"gorev_id": int(gorev_id) }))
        return render_template("gorev.html", aktif_gorev=aktif_gorev, gorevler=gorevler, yapilacaklar=yapilacaklar)

@app.route('/gorev-sil/<gorev_id>', methods=["POST"])
def gorev_sil(gorev_id):
    db["gorevler"].delete_one({"_id": int(gorev_id)})
    return redirect("/", 302)
@app.route('/uye-ol', methods=["GET", "POST"])
def uye_ol():
    if request.method == 'GET':
        return render_template("uye-ol.html")
    else:
        # Formdan gelen verileri al
        email = request.form["email"]
        sifre = request.form["sifre"]
        adsoyad = request.form["adsoyad"]

        # Verileri collection'a ekle
        db["kullanicilar"].insert_one({
            "_id": email,
            "sifre": sifre,
            "adsoyad": adsoyad
        })
        return redirect("/giris", 302)

@app.route('/giris', methods=["GET", "POST"])
def giris():
    if request.method == 'GET':
        return render_template("giris.html")
    else:
        # Formdan gelen verileri al
        email = request.form["email"]
        sifre = request.form["sifre"]

        kullanici = db["kullanicilar"].find_one({"_id": email})

        if kullanici and kullanici["sifre"] == sifre:
            session['kullanici'] = kullanici
            return redirect("/", 302)
        else:
            return "Kullanıcı bulunamadı ya da şifre geçersiz"

@app.route('/cikis', methods=["GET", "POST"])
def cikis():
    session.pop('kullanici', None)
    return redirect("/", 302)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
