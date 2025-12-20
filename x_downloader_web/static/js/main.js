/**
 * X Downloader Web - Main JavaScript
 * Complete version with Telegram upload functionality
 */

// ==================== GLOBAL VARIABLES ====================

let currentTaskId = null;
let websocket = null;
let files = [];
let tasks = [];
let autoRefresh = true;
let selectedFiles = new Set();
let allFiles = [];
let uploadTaskId = null;
let uploadWebSocket = null;

// ==================== DOM READY ====================

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    loadInitialData();
    startAutoRefresh();
});

// ==================== APP INITIALIZATION ====================

function initializeApp() {
    console.log('X Downloader Web v2.0.0 initialized');
    
    // Check connection
    checkConnection();
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Load telegram config from localStorage
    const botToken = localStorage.getItem('telegram_bot_token');
    const chatId = localStorage.getItem('telegram_chat_id');
    
    if (botToken) document.getElementById('botToken').value = botToken;
    if (chatId) document.getElementById('chatId').value = chatId;
}

// ==================== EVENT LISTENERS ====================

function setupEventListeners() {
    // Download button
    document.getElementById('downloadBtn').addEventListener('click', startDownload);
    
    // Clear button
    document.getElementById('clearBtn').addEventListener('click', clearInput);
    
    // Refresh files button
    document.getElementById('refreshFiles').addEventListener('click', loadFiles);
    
    // Clear all files button
    document.getElementById('confirmClearAll').addEventListener('click', clearAllFiles);
    
    // File filter buttons
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active state
            document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Filter files
            const filter = this.getAttribute('data-filter');
            filterFiles(filter);
        });
    });
    
    // Sort buttons
    document.querySelectorAll('[data-sort]').forEach(btn => {
        btn.addEventListener('click', function() {
            const sortBy = this.getAttribute('data-sort');
            sortFiles(sortBy);
        });
    });
    
    // URL input validation
    document.getElementById('urlInput').addEventListener('input', validateURLs);
}

// ==================== CONNECTION MANAGEMENT ====================

async function checkConnection() {
    try {
        const response = await fetch('/api/health');
        if (response.ok) {
            updateConnectionStatus('connected');
        } else {
            updateConnectionStatus('disconnected');
        }
    } catch (error) {
        updateConnectionStatus('disconnected');
        console.error('Connection error:', error);
    }
}

function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connectionStatus');
    switch(status) {
        case 'connected':
            statusElement.className = 'badge bg-success';
            statusElement.textContent = 'Connected';
            break;
        case 'disconnected':
            statusElement.className = 'badge bg-danger';
            statusElement.textContent = 'Disconnected';
            break;
        default:
            statusElement.className = 'badge bg-warning';
            statusElement.textContent = 'Unknown';
    }
}

// ==================== DATA LOADING ====================

async function loadInitialData() {
    await Promise.all([
        loadFiles(),
        loadTasks(),
        loadStats()
    ]);
}

// ==================== DOWNLOAD FUNCTIONALITY ====================

function validateURLs() {
    const textarea = document.getElementById('urlInput');
    const value = textarea.value.trim();
    
    if (!value) {
        return false;
    }
    
    // Simple URL validation
    const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/g;
    const matches = value.match(urlPattern);
    
    const count = matches ? matches.length : 0;
    
    // Update UI based on validation
    const downloadBtn = document.getElementById('downloadBtn');
    if (count > 0) {
        downloadBtn.disabled = false;
        if (count > 1) {
            showToast(`Found ${count} URLs`, 'info');
        }
    } else {
        downloadBtn.disabled = true;
    }
    
    return count > 0;
}

async function startDownload() {
    const urls = document.getElementById('urlInput').value;
    const contentType = document.querySelector('input[name="contentType"]:checked').value;
    const quality = document.querySelector('input[name="quality"]:checked').value;
    
    // Parse URLs
    const urlList = parseURLs(urls);
    
    if (urlList.length === 0) {
        Swal.fire({
            icon: 'warning',
            title: 'No URLs Found',
            text: 'Please enter at least one valid URL.',
            confirmButtonColor: '#1DA1F2'
        });
        return;
    }
    
    // Show progress section
    const progressSection = document.getElementById('progressSection');
    progressSection.style.display = 'block';
    
    // Reset progress
    updateProgress(0, 0, urlList.length, 'Starting download...');
    
    // Disable download button
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
    
    try {
        // Start download task
        const response = await fetch('/api/download/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                urls: urlList,
                content_type: contentType,
                quality: quality
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        currentTaskId = data.task_id;
        
        // Show success message
        showToast(`Download started for ${urlList.length} URLs`, 'success');
        
        // Connect to WebSocket for real-time updates
        connectWebSocket(currentTaskId);
        
        // Poll task status as fallback
        pollTaskStatus(currentTaskId);
        
    } catch (error) {
        console.error('Download error:', error);
        
        Swal.fire({
            icon: 'error',
            title: 'Download Failed',
            text: error.message || 'Failed to start download. Please try again.',
            confirmButtonColor: '#E0245E'
        });
        
        // Reset UI
        resetDownloadUI();
    }
}

function parseURLs(text) {
    if (!text) return [];
    
    // Split by new lines, spaces, commas, or pipes
    const lines = text.split(/[\n\s,|]+/);
    
    // Filter and clean URLs
    const urlPattern = /https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)/;
    
    return lines
        .map(url => url.trim())
        .filter(url => {
            // Remove empty strings and validate URL pattern
            if (!url) return false;
            
            // Check if it's a Twitter/X URL
            if (!url.includes('x.com') && !url.includes('twitter.com')) {
                console.warn(`Skipping non-Twitter URL: ${url}`);
                return false;
            }
            
            return urlPattern.test(url);
        });
}

// ==================== WEBSOCKET HANDLING ====================

function connectWebSocket(taskId) {
    if (websocket) {
        websocket.close();
    }
    
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/tasks/${taskId}`;
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function() {
        console.log('WebSocket connected');
    };
    
    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.type === 'ping') {
            return; // Ignore ping messages
        }
        
        // Update UI with task data
        updateTaskUI(data);
        
        // If task is completed, load files and tasks
        if (data.status === 'completed') {
            loadFiles();
            loadTasks();
            loadStats();
            
            // Show completion message
            showCompletionMessage(data);
        }
    };
    
    websocket.onclose = function() {
        console.log('WebSocket disconnected');
        websocket = null;
    };
    
    websocket.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
}

// ==================== TASK MANAGEMENT ====================

async function pollTaskStatus(taskId) {
    if (!taskId) return;
    
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            const task = await response.json();
            
            updateTaskUI(task);
            
            // Stop polling if task is completed or failed
            if (task.status === 'completed' || task.status === 'failed') {
                clearInterval(pollInterval);
                
                if (task.status === 'completed') {
                    loadFiles();
                    loadTasks();
                    loadStats();
                    showCompletionMessage(task);
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 3000); // Poll every 3 seconds
}

function updateTaskUI(task) {
    // Update progress bar
    const progressBar = document.getElementById('progressBar');
    progressBar.style.width = `${task.progress}%`;
    progressBar.textContent = `${Math.round(task.progress)}%`;
    
    // Update status text
    const statusText = document.getElementById('statusText');
    const progressText = document.getElementById('progressText');
    
    statusText.textContent = task.status.charAt(0).toUpperCase() + task.status.slice(1);
    progressText.textContent = `${task.processed_urls}/${task.total_urls} URLs processed`;
    
    // Update task details
    const taskDetails = document.getElementById('taskDetails');
    taskDetails.innerHTML = `
        <div class="card bg-dark">
            <div class="card-body">
                <h6>Task Details</h6>
                <div class="row">
                    <div class="col-md-6">
                        <small class="text-muted">Task ID:</small>
                        <p class="mb-2"><code>${task.task_id}</code></p>
                    </div>
                    <div class="col-md-6">
                        <small class="text-muted">Files Downloaded:</small>
                        <p class="mb-2">${task.downloaded_files?.length || 0}</p>
                    </div>
                    <div class="col-md-6">
                        <small class="text-muted">Total Size:</small>
                        <p class="mb-2">${task.total_size_mb || 0} MB</p>
                    </div>
                    <div class="col-md-6">
                        <small class="text-muted">Errors:</small>
                        <p class="mb-2">${task.errors?.length || 0}</p>
                    </div>
                </div>
                ${task.errors?.length > 0 ? `
                <div class="mt-2">
                    <small class="text-muted">Recent Errors:</small>
                    <div class="small text-danger">
                        ${task.errors.slice(0, 3).map(e => `<div>${e.url?.substring(0, 50)}... - ${e.error}</div>`).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        </div>
    `;
}

function showCompletionMessage(task) {
    const filesCount = task.downloaded_files?.length || 0;
    const progressSection = document.getElementById('progressSection');
    
    if (filesCount > 0) {
        showToast(`Download completed! ${filesCount} files downloaded.`, 'success');
        
        // Reset UI after a delay
        setTimeout(() => {
            resetDownloadUI();
            progressSection.style.display = 'none';
        }, 3000);
    } else {
        showToast('Download completed but no files were downloaded.', 'warning');
        resetDownloadUI();
    }
}

function resetDownloadUI() {
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<i class="fas fa-play-circle me-2"></i>Start Download';
    
    // Clear progress
    const progressBar = document.getElementById('progressBar');
    progressBar.style.width = '0%';
    progressBar.textContent = '';
    
    // Clear task details
    document.getElementById('taskDetails').innerHTML = '';
}

function clearInput() {
    document.getElementById('urlInput').value = '';
    document.getElementById('progressSection').style.display = 'none';
    resetDownloadUI();
}

// ==================== FILE MANAGEMENT ====================

async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        if (!response.ok) throw new Error('Failed to load files');
        
        files = await response.json();
        renderFilesTable();
        updateFilesCount();
        
    } catch (error) {
        console.error('Error loading files:', error);
        showToast('Failed to load files', 'error');
    }
}

function renderFilesTable() {
    allFiles = files; // Store files globally
    
    const tbody = document.getElementById('filesTable');
    const noFiles = document.getElementById('noFiles');
    const loading = document.getElementById('filesLoading');
    
    // Hide loading
    if (loading) loading.style.display = 'none';
    
    if (files.length === 0) {
        tbody.innerHTML = '';
        noFiles.style.display = 'block';
        updateUploadButtonState();
        return;
    }
    
    noFiles.style.display = 'none';
    
    // Render files with checkboxes
    tbody.innerHTML = files.map(file => {
        const isVideo = file.type === 'video';
        const isSelected = selectedFiles.has(file.name);
        
        return `
        <tr class="file-item ${isSelected ? 'table-primary' : ''}" data-type="${file.type}" data-file="${file.name}">
            <td onclick="event.stopPropagation()">
                <input type="checkbox" 
                       class="form-check-input file-checkbox" 
                       value="${file.name}" 
                       ${isSelected ? 'checked' : ''}
                       onchange="toggleFileSelection(this, '${file.name}')">
            </td>
            <td onclick="selectFileRow(this)">
                ${file.type === 'video' ? 
                    '<i class="fas fa-video text-danger"></i>' : 
                    '<i class="fas fa-image text-success"></i>'}
                <strong class="ms-2">${escapeHtml(file.name)}</strong>
                ${file.resolution ? `<br><small class="text-muted">${file.resolution}</small>` : ''}
            </td>
            <td onclick="selectFileRow(this)">
                <span class="badge ${file.type === 'video' ? 'badge-video' : 'badge-image'}">
                    ${file.type === 'video' ? 'Video' : 'Image'}
                </span>
            </td>
            <td onclick="selectFileRow(this)">${file.size_mb} MB</td>
            <td onclick="selectFileRow(this)">
                <small>${formatDate(file.modified)}</small>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <a href="/download/${encodeURIComponent(file.name)}" 
                       class="btn btn-success" 
                       download="${file.name}"
                       data-bs-toggle="tooltip"
                       title="Download">
                        <i class="fas fa-download"></i>
                    </a>
                    <button onclick="previewFile('${file.name}', '${file.type}')" 
                            class="btn btn-info"
                            data-bs-toggle="tooltip"
                            title="Preview">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button onclick="uploadSingle('${file.name}')" 
                            class="btn btn-telegram"
                            data-bs-toggle="tooltip"
                            title="Upload to Telegram">
                        <i class="fab fa-telegram-plane"></i>
                    </button>
                    <button onclick="deleteFile('${file.name}')" 
                            class="btn btn-danger"
                            data-bs-toggle="tooltip"
                            title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
        `;
    }).join('');
    
    // Re-initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    updateUploadButtonState();
    updateSelectionInfo();
    updateSelectAllCheckbox();
}

function updateFilesCount() {
    const countElement = document.getElementById('filesCount');
    if (countElement) {
        countElement.textContent = files.length;
    }
}

function filterFiles(filter) {
    const rows = document.querySelectorAll('.file-item');
    
    rows.forEach(row => {
        if (filter === 'all' || row.getAttribute('data-type') === filter) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function sortFiles(sortBy) {
    switch(sortBy) {
        case 'newest':
            files.sort((a, b) => new Date(b.modified) - new Date(a.modified));
            break;
        case 'largest':
            files.sort((a, b) => b.size_mb - a.size_mb);
            break;
        case 'name':
            files.sort((a, b) => a.name.localeCompare(b.name));
            break;
        default:
            files.sort((a, b) => new Date(b.modified) - new Date(a.modified));
    }
    
    renderFilesTable();
}

// ==================== FILE ACTIONS ====================

function previewFile(filename, type) {
    if (type === 'video') {
        Swal.fire({
            title: 'Video Preview',
            html: `
                <div class="text-center">
                    <video controls width="100%" style="max-width: 500px;">
                        <source src="/download/${encodeURIComponent(filename)}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                    <p class="mt-2"><strong>${filename}</strong></p>
                </div>
            `,
            showCloseButton: true,
            showConfirmButton: false,
            width: '600px'
        });
    } else if (type === 'image') {
        Swal.fire({
            title: 'Image Preview',
            html: `
                <div class="text-center">
                    <img src="/download/${encodeURIComponent(filename)}" 
                         alt="${filename}" 
                         style="max-width: 100%; max-height: 500px; border-radius: 10px;">
                    <p class="mt-2"><strong>${filename}</strong></p>
                </div>
            `,
            showCloseButton: true,
            showConfirmButton: false,
            width: '600px'
        });
    }
}

async function deleteFile(filename) {
    const result = await Swal.fire({
        title: 'Delete File?',
        text: `Are you sure you want to delete "${filename}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#E0245E',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, delete it!',
        cancelButtonText: 'Cancel'
    });
    
    if (result.isConfirmed) {
        try {
            const response = await fetch(`/api/files/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                showToast('File deleted successfully', 'success');
                loadFiles(); // Refresh list
                // Remove from selection if selected
                selectedFiles.delete(filename);
                updateUploadButtonState();
            } else {
                throw new Error('Failed to delete file');
            }
        } catch (error) {
            console.error('Error deleting file:', error);
            showToast('Failed to delete file', 'error');
        }
    }
}

async function clearAllFiles() {
    const result = await Swal.fire({
        title: 'Clear All Files?',
        text: 'This will permanently delete all downloaded files. This action cannot be undone.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#E0245E',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, delete all!',
        cancelButtonText: 'Cancel'
    });
    
    if (result.isConfirmed) {
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('clearAllModal'));
        modal.hide();
        
        try {
            // Delete each file one by one to avoid overwhelming the server
            for (const file of files) {
                await fetch(`/api/files/${encodeURIComponent(file.name)}`, {
                    method: 'DELETE'
                });
            }
            
            showToast('All files deleted successfully', 'success');
            loadFiles(); // Refresh list
            // Clear selection
            selectedFiles.clear();
            updateUploadButtonState();
        } catch (error) {
            console.error('Error clearing files:', error);
            showToast('Failed to clear all files', 'error');
        }
    }
}

// ==================== TASKS MANAGEMENT ====================

async function loadTasks() {
    try {
        const response = await fetch('/api/tasks?limit=5');
        if (!response.ok) throw new Error('Failed to load tasks');
        
        tasks = await response.json();
        renderTasks();
        updateTasksCount();
        
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

function renderTasks() {
    const tasksList = document.getElementById('tasksList');
    
    if (tasks.length === 0) {
        tasksList.innerHTML = `
            <div class="col-12 text-center py-4">
                <i class="fas fa-history fa-3x text-muted mb-3"></i>
                <h5>No Recent Tasks</h5>
                <p class="text-muted">Start a download to see tasks here.</p>
            </div>
        `;
        return;
    }
    
    tasksList.innerHTML = tasks.map(task => `
        <div class="col-md-6 col-lg-4 mb-3">
            <div class="task-card ${task.status}">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="mb-0">${formatTaskId(task.task_id)}</h6>
                        <small class="text-muted">${formatDate(task.start_time)}</small>
                    </div>
                    <span class="badge ${getStatusBadgeClass(task.status)}">
                        ${task.status}
                    </span>
                </div>
                
                <div class="progress mb-2" style="height: 5px;">
                    <div class="progress-bar ${getProgressBarClass(task.status)}" 
                         style="width: ${task.progress}%"></div>
                </div>
                
                <div class="row small text-muted">
                    <div class="col-6">
                        <i class="fas fa-link"></i> ${task.total_urls} URLs
                    </div>
                    <div class="col-6 text-end">
                        <i class="fas fa-file"></i> ${task.downloaded_files?.length || 0} files
                    </div>
                </div>
                
                ${task.errors?.length > 0 ? `
                <div class="mt-2">
                    <small class="text-danger">
                        <i class="fas fa-exclamation-triangle"></i> ${task.errors.length} errors
                    </small>
                </div>
                ` : ''}
                
                <button onclick="viewTaskDetails('${task.task_id}')" 
                        class="btn btn-sm btn-outline-primary w-100 mt-2">
                    <i class="fas fa-info-circle"></i> Details
                </button>
            </div>
        </div>
    `).join('');
}

async function viewTaskDetails(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`);
        const task = await response.json();
        
        const modalContent = document.getElementById('taskDetailsContent');
        modalContent.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <strong>Task ID:</strong>
                    <p><code>${task.task_id}</code></p>
                </div>
                <div class="col-md-6">
                    <strong>Status:</strong>
                    <p><span class="badge ${getStatusBadgeClass(task.status)}">${task.status}</span></p>
                </div>
                <div class="col-md-6">
                    <strong>Start Time:</strong>
                    <p>${formatDateTime(task.start_time)}</p>
                </div>
                <div class="col-md-6">
                    <strong>End Time:</strong>
                    <p>${task.end_time ? formatDateTime(task.end_time) : 'In progress'}</p>
                </div>
                <div class="col-md-6">
                    <strong>Progress:</strong>
                    <p>${task.progress}% (${task.processed_urls}/${task.total_urls} URLs)</p>
                </div>
                <div class="col-md-6">
                    <strong>Total Size:</strong>
                    <p>${task.total_size_mb || 0} MB</p>
                </div>
            </div>
            
            <h6 class="mt-3">Downloaded Files (${task.downloaded_files?.length || 0})</h6>
            ${task.downloaded_files?.length > 0 ? `
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>File</th>
                            <th>Type</th>
                            <th>Size</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${task.downloaded_files.slice(0, 10).map(file => `
                        <tr>
                            <td>${file.name}</td>
                            <td><span class="badge ${file.type === 'video' ? 'badge-video' : 'badge-image'}">${file.type}</span></td>
                            <td>${file.size_mb} MB</td>
                        </tr>
                        `).join('')}
                    </tbody>
                </table>
                ${task.downloaded_files.length > 10 ? `<p class="text-muted">... and ${task.downloaded_files.length - 10} more files</p>` : ''}
            </div>
            ` : '<p class="text-muted">No files downloaded</p>'}
            
            ${task.errors?.length > 0 ? `
            <h6 class="mt-3">Errors (${task.errors.length})</h6>
            <div class="alert alert-danger">
                <ul class="mb-0">
                    ${task.errors.slice(0, 5).map(error => `<li>${error.url?.substring(0, 50)}... - ${error.error}</li>`).join('')}
                </ul>
                ${task.errors.length > 5 ? `<p class="mt-2 mb-0">... and ${task.errors.length - 5} more errors</p>` : ''}
            </div>
            ` : ''}
        `;
        
        const modal = new bootstrap.Modal(document.getElementById('taskDetailsModal'));
        modal.show();
        
    } catch (error) {
        console.error('Error loading task details:', error);
        showToast('Failed to load task details', 'error');
    }
}

function updateTasksCount() {
    const countElement = document.getElementById('tasksCount');
    if (countElement) {
        countElement.textContent = tasks.length;
    }
}

// ==================== STATISTICS ====================

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        renderStats(stats);
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function renderStats(stats) {
    const statsCards = document.getElementById('statsCards');
    
    if (!statsCards) return;
    
    // Calculate additional stats from files
    const videoFiles = files.filter(f => f.type === 'video');
    const imageFiles = files.filter(f => f.type === 'image');
    const totalSize = files.reduce((sum, file) => sum + file.size_mb, 0);
    
    statsCards.innerHTML = `
        <div class="col-md-3 col-6 mb-3">
            <div class="stat-card">
                <i class="fas fa-download text-primary"></i>
                <div class="stat-value">${stats.total_downloads || files.length}</div>
                <div class="stat-label">Total Downloads</div>
            </div>
        </div>
        <div class="col-md-3 col-6 mb-3">
            <div class="stat-card">
                <i class="fas fa-video text-danger"></i>
                <div class="stat-value">${videoFiles.length}</div>
                <div class="stat-label">Videos</div>
            </div>
        </div>
        <div class="col-md-3 col-6 mb-3">
            <div class="stat-card">
                <i class="fas fa-image text-success"></i>
                <div class="stat-value">${imageFiles.length}</div>
                <div class="stat-label">Images</div>
            </div>
        </div>
        <div class="col-md-3 col-6 mb-3">
            <div class="stat-card">
                <i class="fas fa-database text-warning"></i>
                <div class="stat-value">${totalSize.toFixed(0)}</div>
                <div class="stat-label">Total MB</div>
            </div>
        </div>
    `;
}

// ==================== UPLOAD FUNCTIONALITY ====================

// File selection functions
function toggleFileSelection(checkbox, filename) {
    const row = checkbox.closest('tr');
    
    if (checkbox.checked) {
        selectedFiles.add(filename);
        if (row) row.classList.add('table-primary');
    } else {
        selectedFiles.delete(filename);
        if (row) row.classList.remove('table-primary');
    }
    
    updateUploadButtonState();
    updateSelectionInfo();
    updateSelectAllCheckbox();
}

function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    const rows = document.querySelectorAll('.file-item');
    
    if (checked) {
        // Select all
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            const filename = checkbox.value;
            selectedFiles.add(filename);
        });
        rows.forEach(row => row.classList.add('table-primary'));
    } else {
        // Deselect all
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            const filename = checkbox.value;
            selectedFiles.delete(filename);
        });
        rows.forEach(row => row.classList.remove('table-primary'));
    }
    
    updateUploadButtonState();
    updateSelectionInfo();
}

function selectAllFiles() {
    document.getElementById('selectAllCheckbox').checked = true;
    toggleSelectAll(true);
}

function deselectAllFiles() {
    document.getElementById('selectAllCheckbox').checked = false;
    toggleSelectAll(false);
}

function clearSelection() {
    deselectAllFiles();
}

function updateUploadButtonState() {
    const uploadBtn = document.getElementById('uploadSelectedBtn');
    if (uploadBtn) {
        uploadBtn.disabled = selectedFiles.size === 0;
        uploadBtn.innerHTML = selectedFiles.size === 0 
            ? '<i class="fab fa-telegram-plane me-2"></i>Upload Selected'
            : `<i class="fab fa-telegram-plane me-2"></i>Upload Selected (${selectedFiles.size})`;
    }
}

function updateSelectionInfo() {
    const info = document.getElementById('selectionInfo');
    const count = document.getElementById('selectedCount');
    if (info && count) {
        if (selectedFiles.size > 0) {
            info.style.display = 'flex';
            info.style.alignItems = 'center';
            info.style.justifyContent = 'space-between';
            count.textContent = selectedFiles.size;
        } else {
            info.style.display = 'none';
        }
    }
}

function updateSelectAllCheckbox() {
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const checkboxes = document.querySelectorAll('.file-checkbox');
    
    if (checkboxes.length === 0) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = false;
        return;
    }
    
    const checkedCount = document.querySelectorAll('.file-checkbox:checked').length;
    
    if (checkedCount === 0) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = false;
    } else if (checkedCount === checkboxes.length) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = true;
    } else {
        selectAllCheckbox.indeterminate = true;
        selectAllCheckbox.checked = false;
    }
}

// Helper function for row click selection
function selectFileRow(cell) {
    const row = cell.closest('tr');
    const checkbox = row.querySelector('.file-checkbox');
    const filename = checkbox.value;
    
    checkbox.checked = !checkbox.checked;
    toggleFileSelection(checkbox, filename);
}

// Show upload options
function showUploadOptions() {
    if (selectedFiles.size === 0) {
        showToast('No files selected for upload', 'warning');
        return;
    }

    // Update queue items
    updateUploadQueue();
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('uploadOptionsModal'));
    modal.show();
}

function updateUploadQueue() {
    const queueItems = document.getElementById('uploadQueueItems');
    const count = document.getElementById('uploadQueueCount');
    
    if (selectedFiles.size === 0) {
        queueItems.innerHTML = `
            <div class="text-center py-3">
                <i class="fas fa-inbox fa-2x text-muted mb-2"></i>
                <p class="text-muted">No files selected</p>
            </div>
        `;
        count.textContent = '0';
        return;
    }

    let itemsHTML = '';
    Array.from(selectedFiles).forEach(filename => {
        // Find file info from allFiles array
        const fileInfo = allFiles.find(f => f.name === filename);
        const isVideo = filename.toLowerCase().endsWith('.mp4') || 
                       filename.toLowerCase().endsWith('.mkv') ||
                       filename.toLowerCase().endsWith('.avi');
        
        itemsHTML += `
            <div class="upload-queue-item p-2 mb-2 bg-light rounded">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center">
                        <i class="fas ${isVideo ? 'fa-video text-danger' : 'fa-image text-success'} me-2"></i>
                        <div>
                            <span class="small d-block">${filename}</span>
                            ${fileInfo ? `<small class="text-muted">${fileInfo.size_mb} MB</small>` : ''}
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeFromQueue('${filename}')">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    });

    queueItems.innerHTML = itemsHTML;
    count.textContent = selectedFiles.size;
}

function removeFromQueue(filename) {
    // Uncheck the checkbox
    const checkbox = document.querySelector(`.file-checkbox[value="${filename}"]`);
    if (checkbox) {
        checkbox.checked = false;
        toggleFileSelection(checkbox, filename);
    }
    
    updateUploadQueue();
}

// Start bulk upload
async function startUpload() {
    if (selectedFiles.size === 0) {
        showToast('No files selected for upload', 'warning');
        return;
    }

    const uploadMode = document.getElementById('uploadMode').value;
    const uploadDelay = document.getElementById('uploadDelay').value;
    const addCaption = document.getElementById('addCaption').checked;

    // Close options modal
    const optionsModal = bootstrap.Modal.getInstance(document.getElementById('uploadOptionsModal'));
    if (optionsModal) optionsModal.hide();

    // Show progress modal
    const progressModal = new bootstrap.Modal(document.getElementById('uploadProgressModal'));
    progressModal.show();

    // Update progress UI
    document.getElementById('uploadingFileCount').textContent = selectedFiles.size;
    document.getElementById('uploadedCount').textContent = '0';
    document.getElementById('failedCount').textContent = '0';

    try {
        const response = await fetch('/api/upload/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                filenames: Array.from(selectedFiles),
                upload_mode: uploadMode,
                delay: parseInt(uploadDelay),
                add_caption: addCaption
            })
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }

        const data = await response.json();
        uploadTaskId = data.task_id;

        // Connect to WebSocket for real-time updates
        connectUploadWebSocket(uploadTaskId);

        // Show success message
        showToast(`Upload started for ${selectedFiles.size} files`, 'success');

    } catch (error) {
        console.error('Upload error:', error);
        progressModal.hide();
        Swal.fire({
            icon: 'error',
            title: 'Upload Failed',
            text: error.message || 'Failed to start upload.',
            confirmButtonColor: '#E0245E'
        });
    }
}

// Connect to upload WebSocket
function connectUploadWebSocket(taskId) {
    if (uploadWebSocket) {
        uploadWebSocket.close();
    }

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/tasks/${taskId}`;
    uploadWebSocket = new WebSocket(wsUrl);

    uploadWebSocket.onopen = function() {
        console.log('Upload WebSocket connected');
    };

    uploadWebSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateUploadProgress(data);

        if (data.status === 'completed' || data.status === 'failed') {
            setTimeout(() => {
                showUploadSummary(data);
            }, 1000);
            uploadWebSocket.close();
        }
    };

    uploadWebSocket.onclose = function() {
        console.log('Upload WebSocket disconnected');
        uploadWebSocket = null;
    };

    uploadWebSocket.onerror = function(error) {
        console.error('Upload WebSocket error:', error);
    };
}

function updateUploadProgress(task) {
    // Update overall progress
    const overallProgress = document.getElementById('uploadOverallProgress');
    const uploadStatus = document.getElementById('uploadStatus');
    
    overallProgress.style.width = `${task.progress}%`;
    overallProgress.textContent = `${Math.round(task.progress)}%`;
    uploadStatus.textContent = task.status.charAt(0).toUpperCase() + task.status.slice(1);

    // Update current file progress
    const currentProgress = document.getElementById('uploadCurrentProgress');
    const currentFile = document.getElementById('currentFileName');
    
    if (task.current_file) {
        currentFile.textContent = task.current_file.name;
        currentProgress.style.width = `${task.current_file.progress || 0}%`;
    }

    // Update counts
    const uploadedCount = document.getElementById('uploadedCount');
    const failedCount = document.getElementById('failedCount');
    
    uploadedCount.textContent = task.downloaded_files?.length || 0;
    failedCount.textContent = task.errors?.length || 0;

    // Update details
    const details = document.getElementById('uploadDetails');
    if (task.downloaded_files?.length > 0) {
        const lastFile = task.downloaded_files[task.downloaded_files.length - 1];
        details.innerHTML = `
            <i class="fas fa-check-circle text-success me-2"></i>
            Last uploaded: ${lastFile.name}
        `;
    }
}

function showUploadSummary(task) {
    const progressModal = bootstrap.Modal.getInstance(document.getElementById('uploadProgressModal'));
    if (progressModal) progressModal.hide();

    const summaryContent = document.getElementById('uploadSummaryContent');
    const successCount = task.downloaded_files?.length || 0;
    const failedCount = task.errors?.length || 0;
    const totalCount = successCount + failedCount;

    let summaryHTML = `
        <div class="text-center mb-4">
            <i class="fas ${task.status === 'completed' ? 'fa-check-circle text-success' : 'fa-exclamation-triangle text-warning'} fa-3x mb-3"></i>
            <h4>Upload ${task.status === 'completed' ? 'Complete' : 'Failed'}</h4>
            <p class="text-muted">${totalCount} files processed</p>
        </div>
    `;

    if (successCount > 0) {
        summaryHTML += `
            <div class="alert alert-success">
                <i class="fas fa-check-circle me-2"></i>
                <strong>${successCount} files uploaded successfully</strong>
            </div>
            
            <h6 class="mt-3">Uploaded Files:</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>File</th>
                            <th>Type</th>
                            <th>Size</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        task.downloaded_files.slice(0, 5).forEach(file => {
            summaryHTML += `
                <tr>
                    <td><small>${file.name}</small></td>
                    <td><span class="badge ${file.type === 'video' ? 'bg-danger' : 'bg-success'}">${file.type}</span></td>
                    <td><small>${file.size_mb} MB</small></td>
                </tr>
            `;
        });

        summaryHTML += `
                    </tbody>
                </table>
            </div>
        `;
    }

    if (failedCount > 0) {
        summaryHTML += `
            <div class="alert alert-danger mt-3">
                <i class="fas fa-exclamation-circle me-2"></i>
                <strong>${failedCount} files failed to upload</strong>
            </div>
            
            <h6 class="mt-3">Failed Files:</h6>
            <ul class="list-group">
        `;

        task.errors.slice(0, 3).forEach(error => {
            summaryHTML += `
                <li class="list-group-item">
                    <small class="text-danger">${error.url}</small><br>
                    <small>${error.error}</small>
                </li>
            `;
        });

        summaryHTML += `</ul>`;
    }

    summaryContent.innerHTML = summaryHTML;

    // Clear selection after upload
    deselectAllFiles();

    const summaryModal = new bootstrap.Modal(document.getElementById('uploadCompleteModal'));
    summaryModal.show();
}

// Single file upload
function uploadSingle(filename) {
    // Find file info
    const fileInfo = allFiles.find(f => f.name === filename);
    
    if (!fileInfo) {
        showToast('File not found', 'error');
        return;
    }

    const modal = new bootstrap.Modal(document.getElementById('singleUploadModal'));
    document.getElementById('singleFileName').textContent = filename;
    document.getElementById('singleFileSize').textContent = `Size: ${fileInfo.size_mb} MB`;
    modal.show();
}

async function uploadSingleFile() {
    const filename = document.getElementById('singleFileName').textContent;
    const caption = document.getElementById('singleFileCaption').value;

    try {
        const response = await fetch('/api/upload/single', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                filename: filename,
                caption: caption
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('File uploaded successfully', 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('singleUploadModal'));
            if (modal) modal.hide();
        } else {
            showToast(`Upload failed: ${data.error}`, 'error');
        }
    } catch (error) {
        showToast('Upload failed', 'error');
        console.error(error);
    }
}

// Telegram connection test
async function testTelegramConnection() {
    try {
        showToast('Testing Telegram connection...', 'info');
        const response = await fetch('/api/upload/test-connection');
        const data = await response.json();

        if (data.success) {
            showToast('Telegram connection successful', 'success');
        } else {
            showToast(`Connection failed: ${data.error}`, 'error');
        }
    } catch (error) {
        showToast('Connection test failed', 'error');
    }
}

// Save telegram config
function saveTelegramConfig() {
    const botToken = document.getElementById('botToken').value;
    const chatId = document.getElementById('chatId').value;

    if (!botToken || !chatId) {
        showToast('Please fill in all fields', 'warning');
        return;
    }

    // Save to localStorage
    localStorage.setItem('telegram_bot_token', botToken);
    localStorage.setItem('telegram_chat_id', chatId);

    showToast('Settings saved successfully', 'success');
    const modal = bootstrap.Modal.getInstance(document.getElementById('telegramConfigModal'));
    if (modal) modal.hide();
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        button.classList.remove('fa-eye');
        button.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        button.classList.remove('fa-eye-slash');
        button.classList.add('fa-eye');
    }
}

// ==================== UTILITY FUNCTIONS ====================

function updateProgress(current, total, totalUrls, message) {
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('statusText');
    const progressText = document.getElementById('progressText');
    
    const percentage = total > 0 ? (current / total) * 100 : 0;
    
    progressBar.style.width = `${percentage}%`;
    progressBar.textContent = `${Math.round(percentage)}%`;
    statusText.textContent = message;
    progressText.textContent = `${current}/${totalUrls} URLs`;
}

function startAutoRefresh() {
    if (autoRefresh) {
        setInterval(() => {
            if (!document.hidden) {
                loadTasks();
                loadStats();
            }
        }, 30000); // Refresh every 30 seconds
    }
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'completed': return 'bg-success';
        case 'failed': return 'bg-danger';
        case 'processing': return 'bg-warning';
        case 'pending': return 'bg-info';
        default: return 'bg-secondary';
    }
}

function getProgressBarClass(status) {
    switch(status) {
        case 'completed': return 'bg-success';
        case 'failed': return 'bg-danger';
        case 'processing': return 'progress-bar-animated bg-warning';
        case 'pending': return 'bg-info';
        default: return 'bg-secondary';
    }
}

function formatTaskId(taskId) {
    return taskId.length > 20 ? taskId.substring(0, 20) + '...' : taskId;
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function formatDateTime(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.appendChild(toast);
    
    document.body.appendChild(container);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', function () {
        document.body.removeChild(container);
    });
}

// ==================== EXPORT FUNCTIONS TO GLOBAL SCOPE ====================

window.toggleFileSelection = toggleFileSelection;
window.selectAllFiles = selectAllFiles;
window.deselectAllFiles = deselectAllFiles;
window.clearSelection = clearSelection;
window.showUploadOptions = showUploadOptions;
window.removeFromQueue = removeFromQueue;
window.startUpload = startUpload;
window.uploadSingle = uploadSingle;
window.uploadSingleFile = uploadSingleFile;
window.testTelegramConnection = testTelegramConnection;
window.saveTelegramConfig = saveTelegramConfig;
window.togglePassword = togglePassword;
window.selectFileRow = selectFileRow;
window.previewFile = previewFile;
window.deleteFile = deleteFile;
window.viewTaskDetails = viewTaskDetails;



//NEWWWW