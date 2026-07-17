import os
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
from app.main import extract_linecards, extract_optics, parse_optics, parse_linecards, run_optics_crosscheck_on_data

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'app/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
async def process():
    if 'json_file' not in request.files or 'pdf_file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Missing files'}), 400
    
    json_file = request.files['json_file']
    pdf_file = request.files['pdf_file']
    
    if json_file.filename == '' or pdf_file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected files'}), 400
    
    json_filename = secure_filename(json_file.filename)
    pdf_filename = secure_filename(pdf_file.filename)
    
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], json_filename)
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    
    json_file.save(json_path)
    pdf_file.save(pdf_path)
    
    try:
        linecard_node_ids = await extract_linecards(json_path)
        optics_node_ids = await extract_optics(json_path)
        
        optics_data = await parse_optics(optics_node_ids, json_path, pdf_path)
        linecards = await parse_linecards(linecard_node_ids, json_path, pdf_path)
        
        # Run optics cross-check before returning the result
        linecards = run_optics_crosscheck_on_data(linecards)
        
        return jsonify({
            'status': 'completed',
            'linecard_nodes': linecard_node_ids,
            'optics_nodes': optics_node_ids,
            'optics': optics_data,
            'linecards': linecards
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        # Optional: cleanup uploaded files
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

if __name__ == '__main__':
    # Increase timeout for the development server if supported, 
    # though usually this error comes from a proxy like Nginx or Gunicorn settings.
    app.run(debug=True, port=5001, threaded=True)
