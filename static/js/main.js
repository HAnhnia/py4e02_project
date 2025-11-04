// Cấu hình URL backend
const BACKEND_API_URL = "http://127.0.0.1:5000/api";

// Chạy code khi DOM đã tải xong
document.addEventListener('DOMContentLoaded', () => {
    // Kiểm tra xem chúng ta đang ở trang nào
    const poForm = document.getElementById('po-form');
    const publisherForm = document.getElementById('publisher-form');
    const filterForm = document.getElementById('filter-form');
    const managePage = document.getElementById('manage-page-container'); // [THÊM MỚI]

    if (poForm) {
        initPoForm();
    }
    if (publisherForm) {
        initPublisherForm();
    }
    if (filterForm) {
        initDashboardFilters();
    }
    if (managePage) { // [THÊM MỚI]
        initManagePage();
    }
});

/**
 * Hiển thị thông báo thành công hoặc lỗi
 * @param {string} message - Nội dung thông báo
 * @param {boolean} isError - true nếu là lỗi, false nếu thành công
 */
function showMessage(message, isError = false) {
    const container = document.getElementById('message-container');
    if (!container) return;

    const msgElement = document.createElement('li');
    msgElement.className = isError ? 'message error' : 'message success';
    msgElement.textContent = message;

    container.prepend(msgElement);

    // Tự động xóa thông báo sau 5 giây
    setTimeout(() => {
        msgElement.style.opacity = '0';
        setTimeout(() => msgElement.remove(), 300);
    }, 5000);
}

/**
 * Khởi tạo logic cho trang Khai báo PO
 */
async function initPoForm() {
    const select = document.getElementById('publisher-select');
    const clientCodeInput = document.getElementById('client_code_display');
    const poAmountInput = document.getElementById('po_amount');
    const poAvailableInput = document.getElementById('po_available_amount');
    const form = document.getElementById('po-form');
    // SỬA LỖI: Dùng ID chính xác của nút submit PO
    const submitBtn = document.getElementById('submit-po-btn');

    let publishersData = []; // Lưu trữ dữ liệu publisher

    // Tải danh sách publisher
    try {
        const response = await fetch(`${BACKEND_API_URL}/publishers`);
        if (!response.ok) {
            throw new Error(`Lỗi tải danh sách pháp nhân: ${response.statusText}`);
        }
        publishersData = await response.json();

        select.innerHTML = '<option value="" disabled selected>-- Chọn một pháp nhân --</option>';

        publishersData.forEach(pub => {
            const option = document.createElement('option');
            option.value = pub.ID_phap_nhan;
            option.textContent = `${pub.ten_phap_nhan} (ID: ${pub.ID_phap_nhan})`;
            select.appendChild(option);
        });
    } catch (error) {
        select.innerHTML = '<option value="" disabled selected>Lỗi tải danh sách</option>';
        showMessage(error.message, true);
    }

    // Cập nhật client_code khi chọn publisher
    select.addEventListener('change', () => {
        const selectedId = parseInt(select.value, 10);
        const selectedPub = publishersData.find(p => p.ID_phap_nhan === selectedId);
        if (selectedPub) {
            clientCodeInput.value = selectedPub.client_code;
        }
    });
    
    // Tự động điền po_available_amount
    poAmountInput.addEventListener('input', () => {
        poAvailableInput.value = poAmountInput.value;
    });

    // Xử lý submit form
    form.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        submitBtn.disabled = true;
        submitBtn.textContent = 'Đang xử lý...';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`${BACKEND_API_URL}/create-po`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();
            if (!response.ok || result.success === false) {
                throw new Error(result.message || 'Có lỗi xảy ra khi tạo PO');
            }
            showMessage(`Tạo PO thành công! ID: ${result.new_po_id}, Code: ${result.new_po_code}`, false);
            form.reset(); 
            clientCodeInput.value = '';
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Khai báo PO'; // Đã sửa text hiển thị
        }
    });
}

/**
 * Khởi tạo logic cho trang Khai báo Pháp nhân
 */
function initPublisherForm() {
    const form = document.getElementById('publisher-form');
    // SỬA LỖI: Dùng ID chính xác của nút submit Publisher
    const submitBtn = document.getElementById('submit-publisher-btn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        submitBtn.disabled = true;
        submitBtn.textContent = 'Đang xử lý...';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`${BACKEND_API_URL}/create-publisher`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await response.json();
            if (!response.ok || result.success === false) {
                throw new Error(result.message || 'Có lỗi xảy ra khi tạo pháp nhân');
            }
            showMessage(result.message, false);
            form.reset();
        } catch (error) {
            showMessage(error.message, true);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Khai báo Pháp nhân'; // Đã sửa text hiển thị
        }
    });
}

/// --- DASHBOARD LOGIC (Sửa lỗi tải bảng RFM) ---

/**
 * Lấy các tham số lọc từ form (Giữ nguyên)
 */
function getFilterParams() {
    const form = document.getElementById('filter-form');
    if (!form) return {};
    const formData = new FormData(form);
    const params = {};
    for (const [key, value] of formData.entries()) {
        if (value) {
            params[key] = value;
        }
    }
    return params;
}

/**
 * Tải và hiển thị Bảng Chi tiết Pháp nhân RFM
 */
async function loadRfmDetailTable(filterParams) {
    const container = document.getElementById('rfm-detail-table-container');
    if (!container) return;

    const urlParams = new URLSearchParams(filterParams).toString();
    const apiUrl = `/api/rfm-data?${urlParams}`;
    
    container.innerHTML = `<p>Đang tải dữ liệu RFM...</p>`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`Lỗi HTTP: ${response.status}`);
        }
        const dataJson = await response.json();
        const rfmData = dataJson.data;

        if (rfmData.length === 0) {
            container.innerHTML = '<p>Không tìm thấy Pháp nhân nào khớp với tiêu chí lọc hoặc không có dữ liệu PO hợp lệ.</p>';
            return;
        }

        // Tạo bảng HTML
        let tableHTML = `
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tên Pháp nhân</th>
                            <th>Segment</th>
                            <th title="Recency Score">R</th>
                            <th title="Frequency Score">F</th>
                            <th title="Monetary Score">M</th>
                            <th style="text-align: right;">Recency (Ngày)</th>
                            <th style="text-align: right;">Frequency (Lần)</th>
                            <th style="text-align: right;">Monetary (VNĐ)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        rfmData.forEach(row => {
            const monetaryFormatted = row.Monetary ? new Intl.NumberFormat('vi-VN').format(row.Monetary) : '';

            tableHTML += `
                <tr>
                    <td>${row.ID_phap_nhan}</td>
                    <td>${row.ten_phap_nhan}</td>
                    <td>${row.Segment || ''}</td>
                    <td>${row.R_score || ''}</td>
                    <td>${row.F_score || ''}</td>
                    <td>${row.M_score || ''}</td>
                    <td style="text-align: right;">${row.Recency || ''}</td>
                    <td style="text-align: right;">${row.Frequency || ''}</td>
                    <td style="text-align: right;">${monetaryFormatted}</td>
                </tr>
            `;
        });

        tableHTML += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = tableHTML;
        showMessage(`Đã tải ${rfmData.length} Pháp nhân RFM.`);

    } catch (error) {
        container.innerHTML = `<p class="error">Lỗi tải dữ liệu: ${error.message}</p>`;
        showMessage(`Lỗi tải dữ liệu RFM: ${error.message}`, true);
    }
}


/**
 * Cập nhật tất cả biểu đồ và bảng dựa trên tham số lọc
 */
function updateDashboard(params) {
    const queryString = new URLSearchParams(params).toString();
    
    // Cập nhật URL các biểu đồ PNG
    const monthlyChart = document.getElementById('plot-monthly');
    const campaignChart = document.getElementById('plot-campaign');
    const paretoChart = document.getElementById('plot-pareto');

    if (monthlyChart) monthlyChart.src = `/plot/monthly.png?${queryString}`;
    if (campaignChart) campaignChart.src = `/plot/campaign.png?${queryString}`;
    if (paretoChart) paretoChart.src = `/plot/pareto.png?${queryString}`;

    // GỌI HÀM MỚI: Tải bảng chi tiết RFM
    loadRfmDetailTable(params);
}

function initDashboardFilters() {
    const filterForm = document.getElementById('filter-form');
    
    // 1. Tải dashboard lần đầu
    updateDashboard(getFilterParams()); 

    // 2. Xử lý sự kiện Submit Form (Áp dụng filter)
    filterForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const params = getFilterParams();
        updateDashboard(params);
    });

    // 3. Xử lý nút Reset Form (Xóa filter)
    const resetBtn = document.getElementById('reset-filter-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', (event) => {
            setTimeout(() => {
                // Tải lại dashboard với filter rỗng
                updateDashboard({}); 
            }, 50);
        });
    }
}

/**
 * Tải và hiển thị Bảng Chi tiết Pháp nhân RFM
 */
async function loadRfmDetailTable(filterParams) {
    const container = document.getElementById('rfm-detail-table-container');
    if (!container) return;

    // Chuyển đối tượng filterParams thành chuỗi query string
    const urlParams = new URLSearchParams(filterParams).toString();
    const apiUrl = `/api/rfm-data?${urlParams}`;
    
    container.innerHTML = `<p>Đang tải dữ liệu RFM...</p>`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error('Lỗi khi tải dữ liệu RFM.');
        }
        const dataJson = await response.json();
        const rfmData = dataJson.data;

        if (rfmData.length === 0) {
            container.innerHTML = '<p>Không tìm thấy Pháp nhân nào khớp với tiêu chí lọc.</p>';
            return;
        }

        // Tạo bảng HTML
        let tableHTML = `
            <div class="table-scroll">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tên Pháp nhân</th>
                            <th>Segment</th>
                            <th title="Recency Score">R</th>
                            <th title="Frequency Score">F</th>
                            <th title="Monetary Score">M</th>
                            <th>Recency (Ngày)</th>
                            <th>Frequency (Lần)</th>
                            <th style="text-align: right;">Monetary (VNĐ)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        rfmData.forEach(row => {
            tableHTML += `
                <tr>
                    <td>${row.ID_phap_nhan}</td>
                    <td>${row.ten_phap_nhan}</td>
                    <td>${row.Segment}</td>
                    <td>${row.R_score}</td>
                    <td>${row.F_score}</td>
                    <td>${row.M_score}</td>
                    <td>${row.Recency}</td>
                    <td>${row.Frequency}</td>
                    <td style="text-align: right;">${new Intl.NumberFormat('vi-VN').format(row.Monetary)}</td>
                </tr>
            `;
        });

        tableHTML += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = tableHTML;

    } catch (error) {
        container.innerHTML = `<p class="error">Lỗi tải dữ liệu: ${error.message}</p>`;
    }
}


// --- [PHẦN LOGIC MỚI CHO TRANG QUẢN LÝ] ---

/**
 * Helper để escape HTML, tránh XSS
 */
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return str.toString()
         .replace(/&/g, '&amp;')
         .replace(/</g, '&lt;')
         .replace(/>/g, '&gt;')
         .replace(/"/g, '&quot;')
         .replace(/'/g, '&#039;');
}

/**
 * Khởi tạo logic cho trang Quản lý Dữ liệu
 */
async function initManagePage() {
    const pubTableBody = document.querySelector('#publisher-table tbody');
    const poTableBody = document.querySelector('#po-table tbody');

    if (!pubTableBody || !poTableBody) return;

    // 1. Load data
    try {
        const [pubRes, poRes] = await Promise.all([
            fetch(`${BACKEND_API_URL}/publishers`),
            fetch(`${BACKEND_API_URL}/pos`) // Endpoint mới
        ]);
        
        if (!pubRes.ok || !poRes.ok) {
            throw new Error('Lỗi khi tải dữ liệu từ server');
        }
        
        let publishers = await pubRes.json();
        let pos = await poRes.json();
        
        // ===================================================
        // ✨ THÊM BƯỚC SẮP XẾP GIẢM DẦN THEO ID TẠI ĐÂY ✨
        // ===================================================
        
        // Sắp xếp Pháp nhân (publishers) theo ID_phap_nhan giảm dần
        publishers.sort((a, b) => b.ID_phap_nhan - a.ID_phap_nhan); 
        
        // Sắp xếp PO (pos) theo po_id giảm dần
        pos.sort((a, b) => b.po_id - a.po_id); 

        // ===================================================

        // Render dữ liệu đã được sắp xếp
        renderPublisherTable(publishers, pubTableBody);
        renderPoTable(pos, poTableBody);
        
    } catch (error) {
        showMessage(`Lỗi tải dữ liệu trang quản lý: ${error.message}`, true);
        pubTableBody.innerHTML = `<tr><td colspan="6" style="color: red;">Lỗi tải dữ liệu.</td></tr>`;
        poTableBody.innerHTML = `<tr><td colspan="10" style="color: red;">Lỗi tải dữ liệu.</td></tr>`;
    }
    
    // 2. Thêm event listeners (dùng event delegation)
    pubTableBody.addEventListener('click', handleTableClick);
    poTableBody.addEventListener('click', handleTableClick);
}

/**
 * Vẽ bảng Pháp nhân
 */
function renderPublisherTable(publishers, tbody) {
    // Cột: ID_phap_nhan, ma_phap_nhan, ten_phap_nhan, loai_phap_nhan, client_code
    tbody.innerHTML = '';
    if (publishers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">Không có dữ liệu.</td></tr>';
        return;
    }
    
    for (const pub of publishers) {
        const row = document.createElement('tr');
        row.dataset.id = pub.ID_phap_nhan;
        row.dataset.type = 'publisher';
        row.innerHTML = `
            <td data-field="ID_phap_nhan">${pub.ID_phap_nhan}</td>
            <td data-field="ma_phap_nhan" data-original-value="${escapeHTML(pub.ma_phap_nhan)}">${escapeHTML(pub.ma_phap_nhan)}</td>
            <td data-field="ten_phap_nhan" data-original-value="${escapeHTML(pub.ten_phap_nhan)}">${escapeHTML(pub.ten_phap_nhan)}</td>
            <td data-field="loai_phap_nhan" data-original-value="${escapeHTML(pub.loai_phap_nhan)}">${escapeHTML(pub.loai_phap_nhan)}</td>
            <td data-field="client_code" data-original-value="${escapeHTML(pub.client_code)}">${escapeHTML(pub.client_code)}</td>
            <td class="actions">
                <button class="btn btn-edit">Sửa</button>
            </td>
        `;
        tbody.appendChild(row);
    }
}

/**
 * Vẽ bảng PO
 */
function renderPoTable(pos, tbody) {
    // Cột: po_id, ID_phap_nhan, po_code, po_amount, po_available_amount, po_created_at, po_status, loai_sp, type_po
    tbody.innerHTML = '';
     if (pos.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10">Không có dữ liệu.</td></tr>';
        return;
    }
    
    for (const po of pos) {
        const row = document.createElement('tr');
        row.dataset.id = po.po_id;
        row.dataset.type = 'po';
        
        // Format date (po.po_created_at là 'YYYY-MM-DDTHH:MM:SS')
        const createdAt = po.po_created_at ? new Date(po.po_created_at).toLocaleString('vi-VN') : '';
        const originalDate = po.po_created_at || '';

        row.innerHTML = `
            <td data-field="po_id">${po.po_id}</td>
            <td data-field="ID_phap_nhan" data-original-value="${po.ID_phap_nhan}">${po.ID_phap_nhan}</td>
            <td data-field="po_code" data-original-value="${escapeHTML(po.po_code)}">${escapeHTML(po.po_code)}</td>
            <td data-field="po_amount" data-original-value="${po.po_amount}">${po.po_amount}</td>
            <td data-field="po_available_amount" data-original-value="${po.po_available_amount}">${po.po_available_amount}</td>
            <td data-field="po_created_at" data-original-value="${originalDate}">${createdAt}</td>
            <td data-field="po_status" data-original-value="${escapeHTML(po.po_status)}">${escapeHTML(po.po_status)}</td>
            <td data-field="loai_sp" data-original-value="${escapeHTML(po.loai_sp)}">${escapeHTML(po.loai_sp)}</td>
            <td data-field="type_po" data-original-value="${escapeHTML(po.type_po)}">${escapeHTML(po.type_po)}</td>
            <td class="actions">
                <button class="btn btn-edit">Sửa</button>
            </td>
        `;
        tbody.appendChild(row);
    }
}

/**
 * Xử lý click Sửa / Lưu / Hủy
 */
function handleTableClick(e) {
    const target = e.target;
    const row = target.closest('tr');
    if (!row) return;

    if (target.classList.contains('btn-edit')) {
        handleEditClick(row);
    } else if (target.classList.contains('btn-save')) {
        handleSaveClick(row);
    } else if (target.classList.contains('btn-cancel')) {
        handleCancelClick(row);
    }
}

/**
 * Chuyển hàng sang chế độ Sửa
 */
function handleEditClick(row) {
    const cells = row.querySelectorAll('td[data-field]');
    const type = row.dataset.type;
    
    cells.forEach(cell => {
        const field = cell.dataset.field;
        // Lấy giá trị gốc đã lưu
        const value = cell.dataset.originalValue; 
        
        // Không cho sửa ID
        if (field === 'ID_phap_nhan' && type === 'publisher') return;
        if (field === 'po_id' || field === 'ID_phap_nhan') return;
        // Không cho sửa ngày tạo
        if (field === 'po_created_at') return;

        // Tạo input/select dựa trên field
        if (field === 'loai_phap_nhan') {
            cell.innerHTML = `
                <select name="${field}">
                    <option value="CÔNG TY TNHH" ${value === 'CÔNG TY TNHH' ? 'selected' : ''}>CÔNG TY TNHH</option>
                    <option value="CÔNG TY CỔ PHẦN" ${value === 'CÔNG TY CỔ PHẦN' ? 'selected' : ''}>CÔNG TY CỔ PHẦN</option>
                    <option value="CHI NHÁNH" ${value === 'CHI NHÁNH' ? 'selected' : ''}>CHI NHÁNH</option>
                    <option value="NGÂN HÀNG" ${value === 'NGÂN HÀNG' ? 'selected' : ''}>NGÂN HÀNG</option>
                    <option value="KHÁC" ${value === 'KHÁC' ? 'selected' : ''}>Khác</option>
                    <option value="NHÀ NƯỚC" ${value === 'NHÀ NƯỚC' ? 'selected' : ''}>NHÀ NƯỚC</option>
                    <option value="VĂN PHÒNG ĐẠI DIỆN" ${value === 'VĂN PHÒNG ĐẠI DIỆN' ? 'selected' : ''}>VĂN PHÒNG ĐẠI DIỆN</option>
                </select>`;
        } else if (field === 'loai_sp') {
             cell.innerHTML = `
                <select name="${field}">
                    <option value="Quà vật lý" ${value === 'Quà vật lý' ? 'selected' : ''}>Quà vật lý</option>
                    <option value="Voucher" ${value === 'Voucher' ? 'selected' : ''}>Voucher</option>
                    <option value="Others" ${value === 'Others' ? 'selected' : ''}>Others</option>
                </select>`;
        } else if (field === 'type_po') {
             cell.innerHTML = `
                <select name="${field}">
                    <option value="normal" ${value === 'normal' ? 'selected' : ''}>PO thu tiền</option>
                    <option value="not-in-revenue" ${value === 'not-in-revenue' ? 'selected' : ''}>Không tính doanh thu</option>
                    <option value="testing" ${value === 'testing' ? 'selected' : ''}>PO test</option>
                </select>`;
        } else if (field === 'po_status') {
             cell.innerHTML = `
                <select name="${field}">
                    <option value="Pending" ${value === 'Pending' ? 'selected' : ''}>Pending</option>
                    <option value="Activate" ${value === 'Activate' ? 'selected' : ''}>Activate</option>
                    <option value="Deactivate" ${value === 'Deactivate' ? 'selected' : ''}>Deactivate</option>
                </select>`;
        } else if (field === 'po_amount' || field === 'po_available_amount' || (field === 'ID_phap_nhan' && type === 'po')) {
            cell.innerHTML = `<input type="number" name="${field}" value="${value}">`;
        } else {
            cell.innerHTML = `<input type="text" name="${field}" value="${value}">`;
        }
    });
    
    // Thay đổi nút
    const actionsCell = row.querySelector('.actions');
    actionsCell.innerHTML = `
        <button class="btn btn-save">Lưu</button>
        <button class="btn btn-cancel">Hủy</button>
    `;
}

/**
 * Lưu thay đổi (gọi API PUT)
 */
async function handleSaveClick(row) {
    const id = row.dataset.id;
    const type = row.dataset.type;
    const inputs = row.querySelectorAll('input, select');
    const actionsCell = row.querySelector('.actions');
    
    // Vô hiệu hóa nút
    actionsCell.innerHTML = `<button class="btn" disabled>Đang lưu...</button>`;
    
    const data = {};
    inputs.forEach(input => {
        data[input.name] = input.value;
    });
    
    const url = (type === 'publisher') 
        ? `${BACKEND_API_URL}/publisher/${id}`
        : `${BACKEND_API_URL}/po/${id}`;

    try {
        const response = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        
        if (!response.ok || result.success === false) {
            throw new Error(result.message || 'Lỗi lưu dữ liệu');
        }
        
        showMessage(result.message, false);
        
        // Cập nhật lại UI
        const cells = row.querySelectorAll('td[data-field]');
        cells.forEach(cell => {
            const field = cell.dataset.field;
            
            if (data.hasOwnProperty(field)) {
                const newValue = data[field];
                cell.dataset.originalValue = newValue; // Cập nhật original value
                cell.textContent = newValue; // Cập nhật text hiển thị
            }
        });

        // Khôi phục nút
        actionsCell.innerHTML = `<button class="btn btn-edit">Sửa</button>`;

    } catch (error) {
        showMessage(error.message, true);
        // Có lỗi, khôi phục nút Sửa/Hủy
        actionsCell.innerHTML = `
            <button class="btn btn-save">Lưu</button>
            <button class="btn btn-cancel">Hủy</button>
        `;
    }
}

/**
 * Hủy bỏ Sửa, khôi phục giá trị gốc
 */
function handleCancelClick(row) {
    // Khôi phục lại giá trị cũ
    const cells = row.querySelectorAll('td[data-field]');
    cells.forEach(cell => {
        const field = cell.dataset.field;
        const originalValue = cell.dataset.originalValue;
        
        // ID không đổi
        if ((field === 'ID_phap_nhan' && row.dataset.type === 'publisher') || field === 'po_id') {
            return; 
        }
        
        // Ngày tạo cần format lại
        if (field === 'po_created_at') {
             cell.textContent = originalValue ? new Date(originalValue).toLocaleString('vi-VN') : '';
        } else {
             cell.textContent = originalValue;
        }
    });
    
    // Khôi phục nút
    const actionsCell = row.querySelector('.actions');
    actionsCell.innerHTML = `<button class="btn btn-edit">Sửa</button>`;
}