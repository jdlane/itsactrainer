from flask import Flask, render_template, redirect, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from cs50 import SQL
import random
import os

app = Flask(__name__, static_url_path = "", static_folder = "statics")

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config["TEMPLATES_AUTO_RELOAD"] = True

db = SQL("postgres://clvcdjulxcmawa:dd6973b3af8f46885a3d37b2c9e847d432b71293c7fdaaf939bc8423d7c7f372@ec2-174-129-226-234.compute-1.amazonaws.com:5432/d98vg73hcfavuv")

def blob_to_file(ext, blob):
    blob = bytes(blob)
    blob = str(blob, "utf-8")
    blob = bytearray.fromhex(blob)
    if ext == "png":
        try:
            os.remove("statics/pic.png")
        except:
            print("file not found")
        file = open("statics/pic.png", "x")
        file.close();
        file = open("statics/pic.png", "wb")
        file.write(blob)
        file.close()
        return "pic.png"
    if ext == "jpg" or ext == "jpeg":
        try:
            os.remove("statics/pic.jpg")
        except:
            print("file not found")
        file = open("statics/pic.jpg", "x")
        file.close();
        file = open("statics/pic.jpg", "wb")
        file.write(blob)
        file.close()
        return "pic.jpg"

def get_question(table, qid):
    question = None
    if not session.get("categories"):
        question = db.execute("SELECT question FROM "+table+" WHERE id=:qid", qid=qid)
    else:
        cats = str(session.get("categories")).replace("[","(").replace("]",")")
        if not db.execute("SELECT id FROM "+table+" WHERE id=:qid AND category IN "+cats, qid=qid):
            return "error"
        string = "SELECT question FROM "+table+" WHERE id=:qid AND category IN "+cats
        question = db.execute(string, qid=qid)
    return question

def get_question_and_theme(table, qid):
    question = None
    if not session.get("categories"):
        question = db.execute("SELECT question, theme FROM "+table+" WHERE id=:qid", qid=qid)
    else:
        cats = str(session.get("categories")).replace("[","(").replace("]",")")
        if not db.execute("SELECT id FROM "+table+" WHERE id=:qid AND category IN "+cats, qid=qid):
            return "error"
        string = "SELECT question, theme FROM "+table+" WHERE id=:qid AND category IN "+cats
        question = db.execute(string, qid=qid)
    return question

def get_selected_layout():
    if not session.get("game_layout"):
        return "error"
    arr = []
    for key in session.get("game_layout"):
        if session.get("game_layout")[key]:
            arr.append(str(key))
    return arr

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/error",methods=["GET"])
def error():
    if request.args.get("error"):
        return render_template("error.html",error=request.args.get("error"))
    else:
        return render_template("error.html")

@app.route("/match")
def match():
    return render_template("match.html")

@app.route("/pic")
def pic():
    return session.get("pic")

@app.route("/infinite")
def infinite():
    return render_template("infinite.html")

@app.route("/buzzer")
def buzzer():
    return render_template("buzzer.html")

@app.route("/add", methods=["POST", "GET"])
def add():
    #if get return plain template
    if request.method == "GET":
        return render_template("add.html")
    elif request.method == "POST":
        #if regular question, add to table and return template with standard selected
        question = request.form.get("question")
        answer = request.form.get("answer")
        category = request.form.get("category")
        if category == "category" or not question or not answer:
            return render_template("round1", error="fill all fields")
        #if regular question, add to table and return template
        if not request.form.get("theme") and not request.files["pic"]:
            db.execute("INSERT INTO regulars (question,answer,category) VALUES (:question,:answer,:category)",question=question,answer=answer,category=category)
            return render_template("add.html", type="regular")
        #if theme question, add to table and return template with first round selected and same theme
        if request.form.get("theme") and not request.form.get("pic"):
            theme = request.form.get("theme")
            if not theme:
                return render_template("add.html",error="fill all fields")
            db.execute("INSERT INTO round1 (question,answer,theme,category) VALUES (:question,:answer,:theme,:category)",question=question,answer=answer,theme=theme, category=category)
            return render_template("add.html", type="first", theme=theme)
        #if pic question, convert to byte array then to hex, add to table
        if request.files["pic"] and not request.form.get("theme"):
            pic = request.files["pic"].stream.read()
            filetype = str(request.files["pic"]).split("'")[1].split(".")[1].lower()
            pic = bytearray(pic)
            pic = "".join(format(x, "02x") for x in pic)
            db.execute("INSERT INTO pictures (img, type) VALUES (:img,:type)", img=pic, type=filetype)
            db.execute("INSERT INTO pic_questions (question, answer) VALUES (:question,:answer)",question=question,answer=answer)
            return render_template("add.html", type="pic")

@app.route("/game", methods=["POST"])
def game():
    if request.method == "POST":
        session.clear()
        #set game layout based on user check box input
        gameLayout = {
            "round1": False,
            "individual": False,
            "picture": False,
            "bonus": False,
            "grab bag": False
        }

        round1 = request.form.get("round1")
        picture = request.form.get("picture")
        individual = request.form.get("individual")
        bonus = request.form.get("bonus")
        grabbag = request.form.get("grabbag")
        everything = request.form.get("all")

        if everything:
            gameLayout = {
                "round1": True,
                "individual": True,
                "picture": True,
                "bonus": True,
                "grabbag": True
            }
        if round1:
            gameLayout["round1"] = True
        if picture:
            gameLayout["picture"] = True
        if individual:
            gameLayout["individual"] = True
        if bonus:
            gameLayout["bonus"] = True
        if grabbag:
            gameLayout["grabbag"] = True

        #set session stored question index to 0
        session["question_num"] = 0;

        #set session stored round index to 0
        session["round"] = 0;

        #redirect to home if nothing checked
        if not round1 and not picture and not individual and not bonus and not grabbag and not everything:
            return redirect("/")
        #set session variable to game's round layout
        session["game_layout"] = gameLayout
        #load template of first round chosen
        layout = session.get("game_layout")
        if not layout:
            print("not layout")
            return redirect("/")
        if layout["round1"] == True:
            return redirect("/round1")
        if layout["individual"] == True:
            return redirect("/individual")
        if layout["picture"] == True:
            return redirect("/picture")
        if layout["bonus"] == True:
            return redirect("/bonus")
        if layout["grabbag"] == True:
            return redirect("/grabbag")

@app.route("/round1")
def round1():
    if not session.get("round1"):
        max_id = db.execute("SELECT id FROM round1 ORDER BY id DESC LIMIT 1")[0]["id"]
        question_queue = []
        while len(question_queue) < 8:
            qid = random.randint(1,max_id)
            id_exists = db.execute("SELECT id FROM round1 WHERE id=:qid",qid=qid)
            if not qid in question_queue and id_exists:
                question_queue.append(qid)
        list_string = str(question_queue).replace("[","").replace("]","")
        questions = db.execute("SELECT question, theme, id FROM round1 WHERE id IN (:qids) ORDER BY RANDOM()", qids=question_queue)
        session["round1"] = []
        for question in questions:
            session["round1"].append(question)
    return render_template("round1.html")

@app.route("/picture")
def picture():
    if not session.get("picture"):
        max_id = db.execute("SELECT id FROM pic_questions ORDER BY id DESC LIMIT 1")[0]["id"]
        question_queue = []
        while len(question_queue) < 8:
            qid = random.randint(1,max_id)
            id_exists = db.execute("SELECT id FROM pic_questions WHERE id=:qid",qid=qid)
            if not qid in question_queue and id_exists:
                question_queue.append(qid)
        list_string = str(question_queue).replace("[","").replace("]","")
        questions = db.execute("SELECT question, id FROM pic_questions WHERE id IN (:qids) ORDER BY RANDOM()", qids=question_queue)
        session["picture"] = []
        for question in questions:
            session["picture"].append(question)
    return render_template("picture.html")

@app.route("/questions", methods=["GET"])
def questions():
    if request.args.get("round") == "round1":
        if not session.get("round1"):
            return jsonify("error")
        else:
            num = session.get("question_num")
            session["question_num"] = session["question_num"]+1
            if num>=len(session.get("round1")):
                return jsonify({'last':True})
            dic = session.get("round1")[num]
            dic.update({'last': False})
            return jsonify(dic)
    if request.args.get("round") == "picture":
        if not session.get("picture"):
            return jsonify("error")
        else:
            num = session.get("question_num")
            session["question_num"] = session["question_num"]+1
            if num>=len(session.get("picture")):
                return jsonify({'last':True})
            dic = session.get("picture")[num]
            pic = db.execute("SELECT img, type FROM pictures WHERE id=:qid", qid=dic["id"])
            pic = blob_to_file(pic[0]["type"], pic[0]["img"])
            dic.update({"pic":pic})
            dic.update({'last': False})
            return jsonify(dic)
    if request.args.get("round") == "infinite" and not request.args.get("letters"):
        #set letter index to 0 for buzzer mode
        session["q_letter"] = 0
        #get max ids for each question table
        round1_max = db.execute("SELECT id FROM round1 ORDER BY id DESC LIMIT 1")[0]["id"]
        reg_max = db.execute("SELECT id FROM regulars ORDER BY id DESC LIMIT 1")[0]["id"]
        pic_max = db.execute("SELECT id FROM pic_questions ORDER BY id DESC LIMIT 1")[0]["id"]
        #generate random number from 1 to all max ids combined
        qid = random.randint(1,round1_max+reg_max+pic_max)
        #if random number corresponds with regular question select question and return
        if qid > round1_max and qid <= round1_max+reg_max:
            qid -= round1_max
            question = get_question("regulars",qid)
            #keep getting random row until successful
            while not question:
                qid = random.randint(1,reg_max)
                question = get_question("regulars",qid)
            if question == "error":
                return "error"
            #set session variable for question info
            session["current_question"] = {"table": "regulars", "id": qid}
            return jsonify(question[0])
        #if random number corresponds with themed question, select question and theme and return
        if qid <= round1_max:
            question = get_question_and_theme("round1",qid)
            #keep getting random row until successful
            while not question:
                qid = random.randint(1,round1_max)
                question = get_question_and_theme("round1",qid)
            if question == "error":
                return "error"
            #set session variable for question info
            session["current_question"] = {"table": "round1", "id": qid}
            return jsonify(question[0])
        #if random number corresponds with picture table, select picture and question and return
        if qid > round1_max+reg_max:
            qid -= round1_max+reg_max
            question = get_question("pic_questions",qid)
            #keep getting random row until successful
            while not question:
                qid = random.randint(1,pic_max)
                question = get_question("pic_questions",qid)
            if question == "error":
                return "error"
            #set session variable for question info
            session["current_question"] = {"table": "pic_questions", "id": qid}
            #get pic and save it via blob_to_file
            pic = db.execute("SELECT img, type FROM pictures WHERE id=:qid", qid=qid)
            pic = blob_to_file(pic[0]["type"], pic[0]["img"])
            question[0].update({"pic":pic})
            return jsonify(question[0])
    #if one letter at a time, return next letter of question
    if request.args.get("round") == "infinite" and request.args.get("letters"):
        #track new question by storing question id
        if not session.get("q_letter"):
            session["q_letter"] = 0
        if not session.get("current_question"):
            return jsonify("no question")
        question = db.execute("SELECT question FROM :table WHERE id=:qid", qid=session.get("current_question")["id"], table=session.get("current_question")["table"])
        if session["q_letter"] < len(question[0]["question"]):
            index = session.get("q_letter")
            session["q_letter"] += 1
            return jsonify({"question": question[0]["question"][index], "index": index})
        else:
            return jsonify("last")

@app.route("/answers", methods=["GET"])
def answers():
    if request.args.get("round") == "round1":
        if not session.get("round1"):
            return "error"
        else:
            last = session.get("question_num")<len(session.get("round1"))
            answer = db.execute("SELECT answer FROM round1 WHERE id=:qid", qid=session.get("round1")[session.get("question_num")-1]["id"])
            answer = {"answer": answer[0]["answer"], "last": last}
            return jsonify(answer)
    if request.args.get("round") == "picture":
        if not session.get("picture"):
            return "error"
        else:
            last = session.get("question_num")<len(session.get("picture"))
            answer = db.execute("SELECT answer FROM pic_questions WHERE id=:qid", qid=session.get("picture")[session.get("question_num")-1]["id"])
            answer = {"answer": answer[0]["answer"], "last": last}
            return jsonify(answer)
    if request.args.get("round") == "infinite":
        table = session.get("current_question")["table"]
        qid = session.get("current_question")["id"]
        if table == "round1":
            answer = db.execute("SELECT answer FROM round1 WHERE id=:qid", qid=qid)
        if table == "regulars":
            answer = db.execute("SELECT answer FROM regulars WHERE id=:qid", qid=qid)
        if table == "pic_questions":
            answer = db.execute("SELECT answer FROM pic_questions WHERE id=:qid", qid=qid)
        return jsonify(answer[0]["answer"])

@app.route("/nextround", methods=["GET"])
def next():
    session["round"] = session.get("round")+1
    session["question_num"] = 0
    selected = get_selected_layout()
    if session.get("round") >= len(selected):
        return render_template("match_done.html")
    return redirect("/"+selected[session.get("round")])




@app.route("/cat", methods=["POST","GET"])
def cat():
    #add selected categories to session list
    if request.method == "POST":
        cats = []
        if request.form.get("geo"):
            cats.append("geo")
        if request.form.get("ush"):
            cats.append("ush")
        if request.form.get("world history"):
            cats.append("world history")
        if request.form.get("lit"):
            cats.append("lit")
        if request.form.get("inventors"):
            cats.append("inventors")
        if request.form.get("music"):
            cats.append("music")
        if request.form.get("art"):
            cats.append("art")
        if request.form.get("sci"):
            cats.append("sci")
        if request.form.get("math"):
            cats.append("math")
        if request.form.get("misc"):
            cats.append("misc")
        if request.form.get("all"):
            cats = None
        session["categories"] = cats
        return redirect("/")
    else:
        return render_template("categories.html")
