import os
import sys
import glob
import re
import threading
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from src.database.chroma_client import RikkeiChromaClient
from src.agents.rikkei_agent import RikkeiAgent
from src import config

# Quản lý tiến trình tác vụ bất đồng bộ
tasks_progress = {}
tasks_lock = threading.Lock()
thread_local = threading.local()

class ThreadLocalStdout:
    def __init__(self, original_stdout, tasks_progress):
        self.original_stdout = original_stdout
        self.tasks_progress = tasks_progress

    def write(self, string):
        self.original_stdout.write(string)
        if string.strip():
            task_id = getattr(thread_local, 'task_id', None)
            if task_id:
                with tasks_lock:
                    if task_id in self.tasks_progress:
                        self.tasks_progress[task_id]["logs"].append(string.strip())

    def flush(self):
        self.original_stdout.flush()

# Chuyển hướng stdout để chụp logs theo từng thread
sys.stdout = ThreadLocalStdout(sys.stdout, tasks_progress)

app = Flask(__name__, template_folder='templates', static_folder='templates')

# Khởi tạo các thành phần hệ thống
db_client = RikkeiChromaClient()
agent = RikkeiAgent(chroma_client=db_client)

# Đồng bộ tri thức khi khởi động server
print("[Web Backend] Dang dong bo hoa tai lieu tri thuc ChromaDB...")
db_client.run_sync()
print("[Web Backend] Dong bo hoan tat. San sang phuc vu!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/history', methods=['GET'])
def get_history():
    try:
        md_dir = config.OUTPUT_MD_DIR
        if not os.path.exists(md_dir):
            return jsonify({"status": "success", "files": []})
        
        md_files = glob.glob(os.path.join(md_dir, "*.md"))
        # Sắp xếp theo thời gian sửa đổi giảm dần
        md_files.sort(key=os.path.getmtime, reverse=True)
        
        history = []
        for filepath in md_files:
            filename = os.path.basename(filepath)
            mtime = os.path.getmtime(filepath)
            size = os.path.getsize(filepath)
            
            # Tìm file JSON tương ứng (nếu có)
            json_filename = filename.replace("GiaoAnStandard_", "RawAgent_").replace(".md", ".json")
            has_json = os.path.exists(os.path.join(config.OUTPUT_JSON_DIR, json_filename))
            
            history.append({
                "filename": filename,
                "json_filename": json_filename if has_json else None,
                "size": size,
                "modified": mtime
            })
            
        return jsonify({"status": "success", "files": history})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/view', methods=['GET'])
def view_file():
    try:
        filename = request.args.get('file')
        file_type = request.args.get('type', 'markdown') # markdown hoặc json
        
        if not filename:
            return jsonify({"status": "error", "message": "Thieu tham so 'file'"}), 400
            
        # Bảo vệ chống directory traversal
        filename = os.path.basename(filename)
        
        if file_type == 'markdown':
            filepath = os.path.join(config.OUTPUT_MD_DIR, filename)
        else:
            filepath = os.path.join(config.OUTPUT_JSON_DIR, filename)
            
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": f"Tep tin {filename} khong ton tai"}), 404
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        return jsonify({
            "status": "success",
            "filename": filename,
            "content": content
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_material():
    try:
        data = request.json or {}
        prompt = data.get('prompt', '').strip()
        
        if not prompt:
            return jsonify({"status": "error", "message": "Yeu cau (prompt) khong duoc de trong"}), 400
            
        task_id = str(uuid.uuid4())
        
        with tasks_lock:
            tasks_progress[task_id] = {
                "status": "processing",
                "logs": [],
                "result": None,
                "error_message": None
            }
            
        def run_task(tid, user_prompt):
            thread_local.task_id = tid
            import time
            start_time = time.time() - 2
            try:
                print(f"[Web Backend] Khoi chay Agent voi yeu cau: '{user_prompt}'")
                agent_response = agent.run_agent(user_prompt)
                
                # Tìm file Markdown sinh mới nhất
                md_files = glob.glob(os.path.join(config.OUTPUT_MD_DIR, "*.md"))
                md_content = ""
                md_name = ""
                if md_files:
                    latest_md = max(md_files, key=os.path.getmtime)
                    if os.path.getmtime(latest_md) >= start_time:
                        md_name = os.path.basename(latest_md)
                        with open(latest_md, "r", encoding="utf-8") as f:
                            md_content = f.read()
                            
                # Tìm file JSON sinh mới nhất
                json_files = glob.glob(os.path.join(config.OUTPUT_JSON_DIR, "*.json"))
                json_content = ""
                json_name = ""
                if json_files:
                    latest_json = max(json_files, key=os.path.getmtime)
                    if os.path.getmtime(latest_json) >= start_time:
                        json_name = os.path.basename(latest_json)
                        with open(latest_json, "r", encoding="utf-8") as f:
                            json_content = f.read()
                            
                with tasks_lock:
                    tasks_progress[tid]["result"] = {
                        "agent_response": agent_response,
                        "markdown_name": md_name,
                        "markdown_content": md_content,
                        "json_name": json_name,
                        "json_content": json_content
                    }
                    tasks_progress[tid]["status"] = "success"
                    
            except Exception as ex:
                print(f"[Loi He Thong] Gap su co khi chay Agent: {ex}")
                with tasks_lock:
                    tasks_progress[tid]["status"] = "error"
                    tasks_progress[tid]["error_message"] = str(ex)
        
        t = threading.Thread(target=run_task, args=(task_id, prompt))
        t.daemon = True
        t.start()
        
        return jsonify({
            "status": "processing",
            "task_id": task_id
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_task_status():
    try:
        task_id = request.args.get('task_id')
        if not task_id:
            return jsonify({"status": "error", "message": "Thieu tham so task_id"}), 400
            
        with tasks_lock:
            if task_id not in tasks_progress:
                return jsonify({"status": "error", "message": "Task ID khong ton tai"}), 404
            
            task_info = tasks_progress[task_id]
            return jsonify({
                "status": task_info["status"],
                "logs": task_info["logs"],
                "result": task_info["result"],
                "error_message": task_info["error_message"]
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
