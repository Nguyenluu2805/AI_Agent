import ollama
from src import config

class BaseAgent:
    """
    Lớp Agent cơ sở quản lý kết nối Ollama và Bộ nhớ ngắn hạn (chat history).
    """
    def __init__(self, model_name=config.MODEL_NAME):
        self.model_name = model_name
        self.chat_history = []  # RAM/Short-term memory

    def chat(self, user_message, system_instruction, format_json=True):
        """
        Gửi yêu cầu tới mô hình ngôn ngữ kết hợp System prompt và lịch sử trò chuyện.
        """
        messages = [{"role": "system", "content": system_instruction}]
        
        # Đưa lịch sử chat cũ vào ngữ cảnh
        for past_message in self.chat_history:
            messages.append(past_message)
            
        # Thêm câu hỏi mới của user
        messages.append({"role": "user", "content": user_message})
        
        try:
            if format_json:
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages,
                    format="json"
                )
            else:
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages
                )
                
            response_content = response['message']['content']
            
            # Lưu lượt hội thoại mới vào bộ nhớ ngắn hạn
            self.chat_history.append({"role": "user", "content": user_message})
            self.chat_history.append({"role": "assistant", "content": response_content})
            
            return response_content
        except Exception as e:
            print(f"[Loi] Giao tiep voi Ollama ({self.model_name}): {e}")
            return None

    def clear_memory(self):
        """
        Xóa lịch sử chat của phiên hiện tại.
        """
        self.chat_history = []
        print("[Memory] Da giai phong bo nho ngan han cua Agent.")

    def chat_with_tools(self, user_message, system_instruction, tools_map):
        """
        Vòng lặp ReAct tự trị tự quyết định công cụ chạy bằng định dạng JSON tương thích mọi LLM.
        """
        import json
        
        # Thiết lập tin nhắn ban đầu
        messages = [{"role": "system", "content": system_instruction}]
        
        # Đưa lịch sử chat cũ vào ngữ cảnh
        for past_message in self.chat_history:
            messages.append(past_message)
            
        # Thêm câu hỏi mới của user
        messages.append({"role": "user", "content": user_message})
        
        # Danh sách tin nhắn tạm để lưu lại vào lịch sử sau khi hoàn tất lượt
        new_messages = [{"role": "user", "content": user_message}]
        
        max_steps = 20  # Tránh vòng lặp vô hạn (tăng lên 20 để đủ số bước tự sửa học liệu)
        step = 0
        
        try:
            while step < max_steps:
                step += 1
                print(f"[Ollama] Dang suy nghi...")
                
                # Gọi Ollama chạy ở chế độ ép cấu trúc JSON
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages,
                    format="json"
                )
                
                response_content = response['message']['content']
                
                # Parse cấu trúc suy nghĩ & hành động
                try:
                    step_data = json.loads(response_content)
                except Exception as je:
                    print(f"   [Loi Parse JSON dau ra cua LLM]: {je}")
                    # Gửi tin nhắn yêu cầu sửa đổi JSON
                    error_msg = {
                        "role": "user",
                        "content": f"Lỗi: Bạn đã phản hồi không đúng cấu trúc JSON yêu cầu. Vui lòng thử lại và chỉ trả về cấu trúc: {{\"thought\": \"...\", \"action\": \"...\", \"arguments\": {{...}}}}"
                    }
                    messages.append({"role": "assistant", "content": response_content})
                    messages.append(error_msg)
                    new_messages.append({"role": "assistant", "content": response_content})
                    new_messages.append(error_msg)
                    continue
                
                thought = step_data.get("thought", "Không có mô tả suy nghĩ.")
                action = step_data.get("action")
                arguments = step_data.get("arguments", {})
                
                # Chuẩn hóa trường hợp action là chuỗi "null", "none" hoặc rỗng
                if isinstance(action, str):
                    action_lower = action.strip().lower()
                    if action_lower in ("null", "none", ""):
                        action = None
                
                print(f"[Suy nghi AI]: {thought}")
                
                # Kiểm tra xem có phải hành động kết thúc nhiệm vụ không
                if action == "final_answer":
                    final_response = arguments.get("response", "Nhiem vu da hoan tat.")
                    # Đồng bộ vào lịch sử bộ nhớ ngắn hạn
                    for msg in new_messages:
                        self.chat_history.append(msg)
                    return final_response
                
                # Thực thi tool cục bộ
                if action:
                    print(f"[Hanh dong Agent] Yeu cau goi cong cu: '{action}'")
                    print(f"   Doi so: {arguments}")
                    
                    if action in tools_map:
                        try:
                            # Thực thi hàm
                            result = tools_map[action](**arguments)
                            print(f"   [Ket qua Tool]: Hoan thanh.")
                        except Exception as e:
                            result = f"Loi khi thuc thi cong cu {action}: {str(e)}"
                            print(f"   [Loi Tool]: {result}")
                    else:
                        result = f"Loi: Khong tim thay cong cu '{action}' trong he thong."
                        print(f"   [Loi Tool]: {result}")
                    
                    # Cập nhật kết quả Observation vào hội thoại
                    observation_content = f"Ket qua tu cong cu (Observation) cua '{action}': {result}"
                    
                    messages.append({"role": "assistant", "content": response_content})
                    messages.append({"role": "user", "content": observation_content})
                    
                    new_messages.append({"role": "assistant", "content": response_content})
                    new_messages.append({"role": "user", "content": observation_content})
                else:
                    # Gửi phản hồi lỗi và tiếp tục vòng lặp tự trị
                    print(f"[Canh bao] Agent tra ve action rong (null). Dang yeu cau AI tiep tuc hanh dong...")
                    error_msg = {
                         "role": "user",
                         "content": "Lỗi: Bạn đã thiết lập 'action' là null. Bạn bắt buộc phải gọi một công cụ cụ thể. Hãy tự mình thiết kế bộ bài tập học viên và gọi công cụ 'publish_homework_markdown' với tham số 'homework_json' chứa bộ bài tập đó."
                    }
                    messages.append({"role": "assistant", "content": response_content})
                    messages.append(error_msg)
                    
                    new_messages.append({"role": "assistant", "content": response_content})
                    new_messages.append(error_msg)
                    continue
                    
            print("Dat gioi han so buoc tu duy toi da. Dung Agent.")
            return "Agent dung lai do vuot qua so buoc tu duy toi da."
            
        except Exception as e:
            print(f"[Loi] trong qua trinh chay vong lap Agent: {e}")
            return None
