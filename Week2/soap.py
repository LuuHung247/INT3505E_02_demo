from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
import xml.etree.ElementTree as ET

app = Flask(__name__)

# --- Database config ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

# --- SOAP helper functions ---
def soap_response(body_xml: str):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:user="http://user.com">
  <soap:Header/>
  <soap:Body>
    {body_xml}
  </soap:Body>
</soap:Envelope>
"""

def soap_fault(code: str, reason: str):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <soap:Fault>
      <soap:Code>
        <soap:Value>soap:{code}</soap:Value>
      </soap:Code>
      <soap:Reason>
        <soap:Text xml:lang="en">{reason}</soap:Text>
      </soap:Reason>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>
"""

# --- SOAP Endpoint ---
@app.route('/soap', methods=['POST'])
def soap_service():
    try:
        xml_data = request.data.decode('utf-8')
        root = ET.fromstring(xml_data)
        ns = {
            "soap": "http://www.w3.org/2003/05/soap-envelope",
            "user": "http://user.com"
        }
        body = root.find("soap:Body", ns)
        if body is None:
            return Response(soap_fault("Sender", "Missing SOAP Body"), mimetype="text/xml", status=500)

        # --- GetAllUsers ---
        get_all = body.find("user:GetUsers", ns)
        if get_all is not None:
            users = User.query.all()
            users_xml = "".join(f"""
    <user:User>
      <user:ID>{u.id}</user:ID>
      <user:Name>{u.name}</user:Name>
      <user:Email>{u.email}</user:Email>
    </user:User>""" for u in users)
            body_xml = f"<user:GetUsersResponse>{users_xml}</user:GetUsersResponse>"
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- GetUser ---
        get_user = body.find("user:GetUser", ns)
        if get_user is not None:
            user_id_elem = get_user.find("user:UserID", ns)
            if user_id_elem is None or not user_id_elem.text:
                return Response(soap_fault("Sender", "Missing UserID"), mimetype="text/xml", status=500)
            user = User.query.get(int(user_id_elem.text))
            if not user:
                body_xml = "<user:GetUserResponse><user:Message>User not found</user:Message></user:GetUserResponse>"
            else:
                body_xml = f"""
<user:GetUserResponse>
  <user:User>
    <user:ID>{user.id}</user:ID>
    <user:Name>{user.name}</user:Name>
    <user:Email>{user.email}</user:Email>
  </user:User>
</user:GetUserResponse>
"""
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- CreateUser ---
        create_user = body.find("user:CreateUser", ns)
        if create_user is not None:
            name_elem = create_user.find("user:Name", ns)
            email_elem = create_user.find("user:Email", ns)
            if not name_elem or not name_elem.text or not email_elem or not email_elem.text:
                return Response(soap_fault("Sender", "Missing Name or Email"), mimetype="text/xml", status=500)
            if User.query.filter_by(email=email_elem.text).first():
                body_xml = "<user:CreateUserResponse><user:Message>Email already exists</user:Message></user:CreateUserResponse>"
            else:
                new_user = User(name=name_elem.text, email=email_elem.text)
                db.session.add(new_user)
                db.session.commit()
                body_xml = f"""
<user:CreateUserResponse>
  <user:User>
    <user:ID>{new_user.id}</user:ID>
    <user:Name>{new_user.name}</user:Name>
    <user:Email>{new_user.email}</user:Email>
  </user:User>
</user:CreateUserResponse>
"""
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- UpdateUserEmail ---
        update_email = body.find("user:UpdateUserEmail", ns)
        if update_email is not None:
            user_id_elem = update_email.find("user:UserID", ns)
            email_elem = update_email.find("user:Email", ns)
            if not user_id_elem or not user_id_elem.text or not email_elem or not email_elem.text:
                return Response(soap_fault("Sender", "Missing UserID or Email"), mimetype="text/xml", status=500)
            user = User.query.get(int(user_id_elem.text))
            if not user:
                body_xml = "<user:UpdateUserEmailResponse><user:Message>User not found</user:Message></user:UpdateUserEmailResponse>"
            else:
                user.email = email_elem.text
                db.session.commit()
                body_xml = f"""
<user:UpdateUserEmailResponse>
  <user:User>
    <user:ID>{user.id}</user:ID>
    <user:Name>{user.name}</user:Name>
    <user:Email>{user.email}</user:Email>
  </user:User>
</user:UpdateUserEmailResponse>
"""
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- UpdateUser ---
        update_user = body.find("user:UpdateUser", ns)
        if update_user is not None:
            user_id_elem = update_user.find("user:UserID", ns)
            name_elem = update_user.find("user:Name", ns)
            email_elem = update_user.find("user:Email", ns)
            if not user_id_elem or not user_id_elem.text or not name_elem or not name_elem.text or not email_elem or not email_elem.text:
                return Response(soap_fault("Sender", "Missing fields for UpdateUser"), mimetype="text/xml", status=500)
            user = User.query.get(int(user_id_elem.text))
            if not user:
                body_xml = "<user:UpdateUserResponse><user:Message>User not found</user:Message></user:UpdateUserResponse>"
            else:
                user.name = name_elem.text
                user.email = email_elem.text
                db.session.commit()
                body_xml = f"""
<user:UpdateUserResponse>
  <user:User>
    <user:ID>{user.id}</user:ID>
    <user:Name>{user.name}</user:Name>
    <user:Email>{user.email}</user:Email>
  </user:User>
</user:UpdateUserResponse>
"""
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- DeleteUser ---
        delete_user = body.find("user:DeleteUser", ns)
        if delete_user is not None:
            user_id_elem = delete_user.find("user:UserID", ns)
            if not user_id_elem or not user_id_elem.text:
                return Response(soap_fault("Sender", "Missing UserID for DeleteUser"), mimetype="text/xml", status=500)
            user = User.query.get(int(user_id_elem.text))
            if not user:
                body_xml = "<user:DeleteUserResponse><user:Message>User not found</user:Message></user:DeleteUserResponse>"
            else:
                db.session.delete(user)
                db.session.commit()
                body_xml = f"<user:DeleteUserResponse><user:Message>User deleted</user:Message></user:DeleteUserResponse>"
            return Response(soap_response(body_xml), mimetype="text/xml")

        # --- Unsupported action ---
        return Response(soap_fault("Sender", "Unsupported SOAP action"), mimetype="text/xml", status=500)

    except Exception as e:
        return Response(soap_fault("Receiver", str(e)), mimetype="text/xml", status=500)

# --- Main ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
