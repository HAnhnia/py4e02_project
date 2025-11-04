import pandas as pd
import gspread
import gspread.utils # [THÊM MỚI]
import threading
from flask import Flask, jsonify, request
from google.oauth2.service_account import Credentials
from datetime import datetime
from flask_cors import CORS # Quan trọng: Cho phép frontend gọi

# --- Cấu hình ---
SERVICE_FILE = r"C:\Users\USER\Downloads\mindx_api_key.json"
SHEET_ID = "11v7fwIN2YtrEIq3eAT_duAz-SMUaUIfFm2PEJGzTftI"
# Yêu CẦU QUYỀN GHI
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# --- Khởi tạo ---
try:
    creds = Credentials.from_service_account_file(SERVICE_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    print("Backend: Kết nối Google Sheets thành công!")
except Exception as e:
    print(f"Backend LỖI: Không thể kết nối Google Sheets. Kiểm tra file key và quyền 'Editor'.")
    print(f"Chi tiết lỗi: {e}")
    exit()

# Khóa luồng để tránh 2 người cùng tạo ID mới
data_lock = threading.Lock()

app = Flask(__name__)
# Kích hoạt CORS cho phép frontend (port 8000) gọi
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['JSON_AS_ASCII'] = False

# --- Hàm hỗ trợ Google Sheets ---

def get_worksheet(worksheet_name):
    """Mở một tab (worksheet) từ Sheet."""
    try:
        sheet = client.open_by_key(SHEET_ID)
        return sheet.worksheet(worksheet_name)
    except Exception as e:
        print(f"Lỗi khi mở tab '{worksheet_name}': {e}")
        return None

def get_all_records_as_df(worksheet_name):
    """Đọc toàn bộ dữ liệu từ tab và chuyển sang DataFrame."""
    ws = get_worksheet(worksheet_name)
    if ws is None:
        return pd.DataFrame()
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df

def append_row_to_sheet(worksheet_name, row_data_list):
    """Ghi một dòng mới vào cuối tab."""
    try:
        ws = get_worksheet(worksheet_name)
        if ws:
            ws.append_row(row_data_list, value_input_option='USER_ENTERED')
            return True
        return False
    except Exception as e:
        print(f"Lỗi khi ghi vào Sheet '{worksheet_name}': {e}")
        raise

# --- [HÀM HỖ TRỢ MỚI] ---
def update_sheet_row_by_id(worksheet_name, id_column_name, id_value, new_data_dict):
    """
    Cập nhật một dòng trong sheet dựa vào ID.
    LƯU Ý: Rất quan trọng là new_data_dict PHẢI giữ đúng thứ tự cột như trên GSheet.
    """
    ws = get_worksheet(worksheet_name)
    if not ws:
        raise Exception(f"Không tìm thấy worksheet: {worksheet_name}")

    df = get_all_records_as_df(worksheet_name) # Dùng hàm cũ
    if df.empty:
        raise Exception(f"Không có dữ liệu trong {worksheet_name}")
        
    # Đảm bảo kiểu dữ liệu ID khớp để so sánh
    df[id_column_name] = pd.to_numeric(df[id_column_name], errors='coerce')
    id_value = pd.to_numeric(id_value, errors='coerce')

    # Tìm index của dòng trong DataFrame
    try:
        row_index = df.index[df[id_column_name] == id_value].tolist()[0]
    except IndexError:
        raise Exception(f"Không tìm thấy ID {id_value} trong cột {id_column_name}")

    # GSheet row = DataFrame index + 2 (1 for header, 1 for 0-based index)
    sheet_row_num = row_index + 2
    
    # Lấy header từ sheet (để đảm bảo đúng thứ tự)
    headers = ws.row_values(1)
    
    # Lấy dữ liệu dòng CŨ từ DataFrame (để fill những cột không được update)
    # Phải convert về dict để .get() hoạt động
    old_row_data = df.iloc[row_index].to_dict()
    
    # Tạo list giá trị mới theo đúng thứ tự header
    new_row_values = []
    for col_name in headers:
        col_name_stripped = col_name.strip()
        if col_name_stripped in new_data_dict:
            # Lấy giá trị mới nếu có
            new_row_values.append(new_data_dict[col_name_stripped])
        else:
            # Giữ giá trị cũ nếu không được cung cấp
            new_row_values.append(old_row_data.get(col_name_stripped, "")) # Dùng "" làm default
    
    # Cập nhật GSheet
    cell_range = f'A{sheet_row_num}:{gspread.utils.rowcol_to_a1(sheet_row_num, len(headers))}'
    ws.update(cell_range, [new_row_values], value_input_option='USER_ENTERED')
    return True
# --- [HẾT HÀM MỚI] ---

# --- API Endpoints ---

@app.route('/api/all-data', methods=['GET'])
def api_get_all_data():
    """API: Lấy dữ liệu gộp cho dashboard."""
    try:
        pom = get_all_records_as_df("pom")
        dim = get_all_records_as_df("dim_publisher")

        if pom.empty:
            return jsonify([]) # Trả về mảng rỗng nếu không có dữ liệu

        # Dọn dẹp po_amount
        if 'po_amount' in pom.columns:
            pom['po_amount'] = (
                pom['po_amount'].astype(str).str.replace(",", "", regex=False)
            )
            pom['po_amount'] = pd.to_numeric(pom['po_amount'], errors='coerce').fillna(0)
        else:
            pom['po_amount'] = 0.0

        # Gộp dữ liệu
        if not dim.empty and 'ID_phap_nhan' in pom.columns and 'ID_phap_nhan' in dim.columns:
            pom['ID_phap_nhan'] = pd.to_numeric(pom['ID_phap_nhan'], errors='coerce')
            dim['ID_phap_nhan'] = pd.to_numeric(dim['ID_phap_nhan'], errors='coerce')
            df = pom.merge(dim, on='ID_phap_nhan', how='left')
        else:
            df = pom.copy()

        # Chuẩn hóa ngày
        if 'po_created_at' in df.columns:
             df['po_created_at'] = pd.to_datetime(df['po_created_at'], errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%S')

        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/publishers', methods=['GET'])
def api_get_publishers():
    """API: Lấy danh sách pháp nhân cho dropdown (PO form) VÀ bảng quản lý."""
    try:
        df = get_all_records_as_df("dim_publisher")
        if df.empty:
            return jsonify([])
        
        # Chỉ trả về các cột cần thiết (cho form)
        # Bảng quản lý cần tất cả, nên chúng ta sẽ trả về tất cả
        # cols = ['ID_phap_nhan', 'ten_phap_nhan', 'client_code']
        # df = df[cols]
        return jsonify(df.to_dict('records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- [API MỚI] ---
@app.route('/api/pos', methods=['GET'])
def api_get_pos():
    """API: Lấy danh sách PO (chỉ bảng pom) cho trang quản lý."""
    try:
        df = get_all_records_as_df("pom")
        if df.empty:
            return jsonify([])
        
        # Chuẩn hóa ngày
        if 'po_created_at' in df.columns:
            # Trả về format ISO để JS có thể parse
             df['po_created_at'] = pd.to_datetime(df['po_created_at'], errors='coerce').dt.strftime('%Y-%m-%dT%H:%M:%S')

        return jsonify(df.to_dict('records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# --- [HẾT API MỚI] ---


@app.route('/api/create-publisher', methods=['POST'])
def api_create_publisher():
    """API: Tạo pháp nhân mới."""
    with data_lock: # Khóa để đảm bảo an toàn khi tính ID
        try:
            data = request.json
            df = get_all_records_as_df("dim_publisher")
            
            # --- [PHẦN THÊM MỚI] KIỂM TRA TÍNH DUY NHẤT ---
            new_ma_phap_nhan = data.get('ma_phap_nhan')
            
            # Chỉ kiểm tra nếu người dùng có nhập mã pháp nhân (không rỗng)
            if new_ma_phap_nhan and (not df.empty):
                # Chuyển đổi cột 'ma_phap_nhan' trong DataFrame sang kiểu string
                # để so sánh chính xác (tránh lỗi 123 vs '123')
                existing_codes = df['ma_phap_nhan'].astype(str)
                
                # Kiểm tra xem mã mới (dưới dạng string) đã tồn tại chưa
                if existing_codes.str.fullmatch(str(new_ma_phap_nhan)).any():
                    # Nếu TỒN TẠI, trả về lỗi ngay lập tức
                    return jsonify({
                        "success": False, 
                        "message": f"Lỗi: Mã pháp nhân '{new_ma_phap_nhan}' đã tồn tại. Vui lòng kiểm tra lại."
                    }), 400 # 400 Bad Request
            # --- [HẾT PHẦN THÊM MỚI] ---
            
            # Tính ID mới (giữ nguyên logic cũ)
            if df.empty or 'ID_phap_nhan' not in df.columns:
                new_id = 1
            else:
                new_id = pd.to_numeric(df['ID_phap_nhan'], errors='coerce').max() + 1
            
            # Cột: ID_phap_nhan, ma_phap_nhan, ten_phap_nhan, loai_phap_nhan, client_code
            new_row = [
                int(new_id),
                new_ma_phap_nhan, # Sử dụng biến đã lấy ở trên
                data.get('ten_phap_nhan'),
                data.get('loai_phap_nhan'),
                data.get('client_code')
            ]
            
            append_row_to_sheet("dim_publisher", new_row)
            return jsonify({"success": True, "message": f"Tạo pháp nhân '{data.get('ten_phap_nhan')}' thành công!", "new_id": new_id})
            
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

# --- [API MỚI] ---
@app.route('/api/publisher/<int:id_phap_nhan>', methods=['PUT'])
def api_update_publisher(id_phap_nhan):
    """API: Cập nhật pháp nhân."""
    with data_lock:
        try:
            data = request.json
            # ID_phap_nhan không được sửa
            if 'ID_phap_nhan' in data:
                del data['ID_phap_nhan']
            
            update_sheet_row_by_id(
                "dim_publisher", 
                "ID_phap_nhan", 
                id_phap_nhan, 
                data 
            )
            return jsonify({"success": True, "message": f"Cập nhật pháp nhân ID {id_phap_nhan} thành công."})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
# --- [HẾT API MỚI] ---

@app.route('/api/create-po', methods=['POST'])
def api_create_po():
    """API: Tạo PO mới."""
    with data_lock: # Khóa để đảm bảo an toàn
        try:
            data = request.json
            
            pom_df = get_all_records_as_df("pom")
            dim_df = get_all_records_as_df("dim_publisher")
            
            if dim_df.empty:
                return jsonify({"success": False, "message": "Lỗi: Không có dữ liệu pháp nhân."}), 400

            # 1. Tính po_id
            if pom_df.empty or 'po_id' not in pom_df.columns:
                new_po_id = 1
            else:
                new_po_id = pd.to_numeric(pom_df['po_id'], errors='coerce').max() + 1
            
            # 2. Lấy client_code
            id_phap_nhan = int(data.get('id_phap_nhan'))
            dim_df['ID_phap_nhan'] = pd.to_numeric(dim_df['ID_phap_nhan'], errors='coerce')
            publisher = dim_df[dim_df['ID_phap_nhan'] == id_phap_nhan]
            
            if publisher.empty:
                return jsonify({"success": False, "message": f"Lỗi: Không tìm thấy pháp nhân với ID {id_phap_nhan}"}), 400
            client_code = publisher.iloc[0]['client_code']
            
            # 3. Tính po_created_at
            now = datetime.now()
            created_at_str = now.strftime("%Y-%m-%d %H:%M:%S") # Format cho Google Sheets
            
            # 4. Tính po_code (theo yêu cầu: client_code + _001_ + yymmdd)
            date_code_str = now.strftime("%y%m%d")
            new_po_code = f"{client_code}_001_{date_code_str}"
            
            # 5. Chuẩn bị dòng mới
            # Cột: ID_phap_nhan, po_id, po_code, po_amount, po_available_amount, po_created_at, po_status, loai_sp, type_po
            new_row = [
                id_phap_nhan,
                int(new_po_id),
                new_po_code,
                float(data.get('po_amount', 0)),
                float(data.get('po_available_amount', 0)), # Giả định po_available_amount = po_amount khi mới tạo
                created_at_str,
                data.get('po_status'),
                data.get('loai_sp'),
                data.get('type_po')
            ]
            
            append_row_to_sheet("pom", new_row)
            return jsonify({"success": True, "message": "Tạo PO thành công!", "new_po_id": new_po_id, "new_po_code": new_po_code})

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

# --- [API MỚI] ---
@app.route('/api/po/<int:po_id>', methods=['PUT'])
def api_update_po(po_id):
    """API: Cập nhật PO."""
    with data_lock:
        try:
            data = request.json
            # po_id không được sửa
            if 'po_id' in data:
                del data['po_id']

            if 'ID_phap_nhan' in data:
                del data['ID_phap_nhan']
                        
            # Cột pom: ID_phap_nhan, po_id, po_code, po_amount, po_available_amount, po_created_at, po_status, loai_sp, type_po
            # Cần ép kiểu
            if 'po_amount' in data:
                data['po_amount'] = float(data.get('po_amount', 0))
            if 'po_available_amount' in data:
                data['po_available_amount'] = float(data.get('po_available_amount', 0))
            if 'ID_phap_nhan' in data:
                data['ID_phap_nhan'] = int(data.get('ID_phap_nhan'))

            update_sheet_row_by_id(
                "pom", 
                "po_id", 
                po_id, 
                data
            )
            return jsonify({"success": True, "message": f"Cập nhật PO ID {po_id} thành công."})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
# --- [HẾT API MỚI] ---

if __name__ == '__main__':
    # Chạy backend trên port 5000
    app.run(debug=True, port=5000)