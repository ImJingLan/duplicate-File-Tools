var App = {
    state: {
        currentTab: 'scan',
        currentTaskId: null,
        currentScanPollingId: null,
        pollingIntervalId: null,
        pollingRetryCount: 0,
        maxPollingRetries: 3,
        historyPage: 1,
        historyPageSize: 10,
        historyStatusFilter: 'all',
        patternList: [],
        activeScanTasks: {},
        selectedResultTaskId: null,
        dedupAnalysisResults: null,
        dedupPreviewResults: null,
        generatedScript: null,
        generatedScriptType: null,
        taskRefreshTimer: null
    },

    apiBase: '/api',

    utils: {
        formatBytes: function (bytes) {
            if (bytes === null || bytes === undefined || isNaN(bytes)) return '0 B';
            bytes = parseInt(bytes, 10);
            if (bytes === 0) return '0 B';
            var units = ['B', 'KB', 'MB', 'GB', 'TB'];
            var i = Math.floor(Math.log(bytes) / Math.log(1024));
            i = Math.min(i, units.length - 1);
            return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
        },

        formatDate: function (dateStr) {
            if (!dateStr) return '-';
            try {
                var d = new Date(dateStr);
                if (isNaN(d.getTime())) return dateStr;
                var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
                return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
                    ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
            } catch (e) {
                return dateStr;
            }
        },

        formatTime: function (seconds) {
            if (!seconds || seconds <= 0) return '0s';
            seconds = Math.round(seconds);
            var h = Math.floor(seconds / 3600);
            var m = Math.floor((seconds % 3600) / 60);
            var s = seconds % 60;
            var parts = [];
            if (h > 0) parts.push(h + 'h');
            if (m > 0) parts.push(m + 'm');
            if (s > 0 || parts.length === 0) parts.push(s + 's');
            return parts.join(' ');
        },

        escapeHtml: function (str) {
            if (!str) return '';
            var map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            };
            return str.replace(/[&<>"']/g, function (c) { return map[c]; });
        },

        showToast: function (message, type) {
            type = type || 'info';
            var container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:8px;';
                document.body.appendChild(container);
            }

            var toast = document.createElement('div');
            var colors = {
                info: '#2196F3',
                success: '#4CAF50',
                warning: '#FF9800',
                error: '#F44336'
            };
            var bgColor = colors[type] || colors.info;
            var iconMap = { info: 'ℹ', success: '✓', warning: '⚠', error: '✕' };
            var icon = iconMap[type] || iconMap.info;

            toast.style.cssText = 'background:' + bgColor + ';color:#fff;padding:12px 20px;border-radius:6px;' +
                'box-shadow:0 4px 12px rgba(0,0,0,0.2);font-size:14px;min-width:250px;max-width:450px;' +
                'word-wrap:break-word;display:flex;align-items:center;gap:10px;' +
                'animation:slideInRight 0.3s ease;opacity:1;transition:opacity 0.3s ease;';
            toast.innerHTML = '<span style="font-size:18px;flex-shrink:0;">' + icon + '</span><span>' +
                App.utils.escapeHtml(message) + '</span>';

            container.appendChild(toast);

            setTimeout(function () {
                toast.style.opacity = '0';
                setTimeout(function () {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                        if (container.children.length === 0 && container.parentNode) {
                            container.parentNode.removeChild(container);
                        }
                    }
                }, 300);
            }, 3500);
        },

        showModal: function (title, content, actions) {
            var overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
                'background:rgba(0,0,0,0.5);z-index:9000;display:flex;align-items:center;justify-content:center;';

            var modal = document.createElement('div');
            modal.className = 'modal-dialog';
            modal.style.cssText = 'background:#fff;border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.3);' +
                'min-width:400px;max-width:600px;max-height:80vh;display:flex;flex-direction:column;';

            var header = document.createElement('div');
            header.style.cssText = 'padding:16px 20px;border-bottom:1px solid #e0e0e0;font-size:16px;font-weight:600;';
            header.textContent = title;

            var body = document.createElement('div');
            body.style.cssText = 'padding:20px;overflow-y:auto;flex:1;';
            if (typeof content === 'string') {
                body.innerHTML = content;
            } else {
                body.appendChild(content);
            }

            var footer = document.createElement('div');
            footer.style.cssText = 'padding:12px 20px;border-top:1px solid #e0e0e0;display:flex;justify-content:flex-end;gap:8px;';

            actions = actions || [];
            actions.forEach(function (action) {
                var btn = document.createElement('button');
                btn.textContent = action.text || 'OK';
                btn.style.cssText = 'padding:8px 16px;border-radius:4px;cursor:pointer;font-size:14px;border:none;' +
                    (action.primary
                        ? 'background:#1976D2;color:#fff;'
                        : 'background:#f5f5f5;color:#333;border:1px solid #ddd;');
                btn.addEventListener('click', function () {
                    if (action.callback) {
                        action.callback();
                    }
                    App.utils.closeModal(overlay);
                });
                btn.addEventListener('mouseenter', function () {
                    if (action.primary) {
                        btn.style.background = '#1565C0';
                    } else {
                        btn.style.background = '#e0e0e0';
                    }
                });
                btn.addEventListener('mouseleave', function () {
                    if (action.primary) {
                        btn.style.background = '#1976D2';
                    } else {
                        btn.style.background = '#f5f5f5';
                    }
                });
                footer.appendChild(btn);
            });

            modal.appendChild(header);
            modal.appendChild(body);
            modal.appendChild(footer);
            overlay.appendChild(modal);

            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    App.utils.closeModal(overlay);
                }
            });

            document.body.appendChild(overlay);
            return { overlay: overlay, modal: modal, body: body };
        },

        closeModal: function (overlay) {
            if (overlay && overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        },

        confirmDialog: function (message) {
            return new Promise(function (resolve) {
                var content = '<p style="margin:0;font-size:14px;line-height:1.6;">' +
                    App.utils.escapeHtml(message) + '</p>';
                App.utils.showModal('确认操作', content, [
                    {
                        text: '取消',
                        callback: function () { resolve(false); }
                    },
                    {
                        text: '确认',
                        primary: true,
                        callback: function () { resolve(true); }
                    }
                ]);
            });
        },

        apiRequest: async function (url, options) {
            var defaultHeaders = { 'Content-Type': 'application/json' };
            options = options || {};
            options.headers = Object.assign({}, defaultHeaders, options.headers || {});

            try {
                var response = await fetch(url, options);
                var data;
                var contentType = response.headers.get('content-type') || '';
                if (contentType.indexOf('application/json') !== -1) {
                    data = await response.json();
                } else {
                    data = await response.text();
                }

                if (!response.ok) {
                    var errorMsg = (data && data.error) ? data.error : ('请求失败 (' + response.status + ')');
                    throw new Error(errorMsg);
                }
                return data;
            } catch (err) {
                if (err.name === 'TypeError' && err.message.indexOf('fetch') !== -1) {
                    throw new Error('网络连接失败，请检查服务器是否运行');
                }
                throw err;
            }
        },

        toggleLoading: function (element, loading) {
            if (!element) return;
            if (loading) {
                element.disabled = true;
                element.setAttribute('data-original-text', element.textContent);
                element.textContent = '处理中...';
            } else {
                element.disabled = false;
                var originalText = element.getAttribute('data-original-text');
                if (originalText) {
                    element.textContent = originalText;
                }
            }
        },

        escapeHtmlTruncate: function (str, maxLen) {
            str = str || '';
            if (str.length > maxLen) {
                return App.utils.escapeHtml('...' + str.slice(-(maxLen - 3)));
            }
            return App.utils.escapeHtml(str);
        },

        scrollToElement: function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    },

    tabs: {
        init: function () {
            var self = this;
            var tabButtons = document.querySelectorAll('.tab-nav .tab-btn');
            tabButtons.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tabName = this.getAttribute('data-tab');
                    if (tabName) {
                        self.switchTab(tabName);
                    }
                });
            });
        },

        switchTab: function (tabName) {
            var tabs = ['scan', 'results', 'dedup', 'patterns', 'history'];
            if (tabs.indexOf(tabName) === -1) return;

            App.state.currentTab = tabName;

            var tabButtons = document.querySelectorAll('.tab-nav .tab-btn');
            tabButtons.forEach(function (btn) {
                btn.classList.remove('active');
                if (btn.getAttribute('data-tab') === tabName) {
                    btn.classList.add('active');
                }
            });

            var panels = document.querySelectorAll('.tab-panel');
            panels.forEach(function (panel) {
                panel.style.display = 'none';
            });
            var targetPanel = document.getElementById('tab-' + tabName);
            if (targetPanel) {
                targetPanel.style.display = 'block';
            }

            switch (tabName) {
                case 'scan':
                    App.scan.loadTasks();
                    break;
                case 'results':
                    App.results.loadTaskSelector();
                    break;
                case 'dedup':
                    App.dedup.loadDedupTaskSelector();
                    break;
                case 'patterns':
                    App.patterns.loadPatterns();
                    break;
                case 'history':
                    App.history.loadHistory();
                    break;
            }
        }
    },

    scan: {
        init: function () {
            var self = this;
            var scanForm = document.getElementById('scan-form');
            if (scanForm) {
                scanForm.addEventListener('submit', function (e) {
                    e.preventDefault();
                    self.startScan();
                });
            }

            var stopBtn = document.getElementById('btn-stop-scan');
            if (stopBtn) {
                stopBtn.addEventListener('click', function () {
                    self.stopTask();
                });
            }

            var refreshBtn = document.getElementById('btn-refresh-tasks');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function () {
                    self.loadTasks();
                });
            }

            var clearFinishedBtn = document.getElementById('btn-clear-finished');
            if (clearFinishedBtn) {
                clearFinishedBtn.addEventListener('click', function () {
                    self.clearFinishedTasks();
                });
            }

            this.loadScanFormDefaults();
            this.loadTasks();
        },

        loadScanFormDefaults: function () {
            var dirInput = document.getElementById('scan-directory');
            var minSizeInput = document.getElementById('scan-min-size');
            var excludeInput = document.getElementById('scan-exclude');
            var algoSelect = document.getElementById('scan-algorithm');

            if (dirInput) {
                var saved = localStorage.getItem('dedup_scan_directory') || '';
                dirInput.value = saved;
            }
            if (minSizeInput) minSizeInput.value = '0';
            if (excludeInput) excludeInput.value = '';
            if (algoSelect) algoSelect.value = 'md5';
        },

        getScanFormData: function () {
            var directory = document.getElementById('scan-directory');
            var minSize = document.getElementById('scan-min-size');
            var exclude = document.getElementById('scan-exclude');
            var algorithm = document.getElementById('scan-algorithm');

            directory = directory ? directory.value.trim() : '';
            minSize = minSize ? parseInt(minSize.value, 10) || 0 : 0;
            var excludeRaw = exclude ? exclude.value.trim() : '';
            var excludePatterns = excludeRaw ? excludeRaw.split(',').map(function (s) { return s.trim(); }).filter(function (s) { return s.length > 0; }) : [];
            algorithm = algorithm ? algorithm.value : 'md5';

            return {
                directory: directory,
                min_size: minSize,
                exclude_patterns: excludePatterns,
                algorithm: algorithm
            };
        },

        startScan: async function () {
            var formData = this.getScanFormData();
            if (!formData.directory) {
                App.utils.showToast('请输入扫描目录路径', 'warning');
                return;
            }

            var btn = document.getElementById('btn-start-scan');
            App.utils.toggleLoading(btn, true);

            try {
                var data = await App.utils.apiRequest(App.apiBase + '/scan/start', {
                    method: 'POST',
                    body: JSON.stringify(formData)
                });

                if (formData.directory) {
                    localStorage.setItem('dedup_scan_directory', formData.directory);
                }

                App.state.currentScanPollingId = data.task_id;
                App.utils.showToast('扫描任务已启动: ' + data.task_id, 'success');
                this.showProgressPanel(data.task_id);
                this.pollTaskStatus(data.task_id);
                this.loadTasks();
            } catch (err) {
                App.utils.showToast('启动扫描失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        pollTaskStatus: async function (taskId) {
            var self = this;
            App.state.pollingRetryCount = 0;

            var poll = async function () {
                try {
                    var data = await App.utils.apiRequest(App.apiBase + '/scan/status/' + taskId);
                    self.updateProgressPanel(data);
                    App.state.activeScanTasks[taskId] = data;

                    if (data.status === 'running' || data.status === 'pending') {
                        App.state.pollingIntervalId = setTimeout(poll, 1000);
                    } else {
                        self.stopPolling();
                        if (data.status === 'completed') {
                            App.utils.showToast('扫描完成！共发现文件重复组', 'success');
                        } else if (data.status === 'stopped') {
                            App.utils.showToast('扫描已停止', 'warning');
                        } else if (data.status === 'failed') {
                            App.utils.showToast('扫描失败: ' + (data.error || '未知错误'), 'error');
                        }
                        self.hideProgressPanel();
                        self.loadTasks();
                    }
                } catch (err) {
                    App.state.pollingRetryCount++;
                    if (App.state.pollingRetryCount < App.state.maxPollingRetries) {
                        App.state.pollingIntervalId = setTimeout(poll, 2000);
                    } else {
                        self.stopPolling();
                        App.utils.showToast('轮询任务状态失败: ' + err.message, 'error');
                    }
                }
            };

            poll();
        },

        stopPolling: function () {
            if (App.state.pollingIntervalId) {
                clearTimeout(App.state.pollingIntervalId);
                App.state.pollingIntervalId = null;
            }
        },

        updateProgressPanel: function (data) {
            var panel = document.getElementById('scan-progress-panel');
            if (!panel) return;
            panel.style.display = 'block';

            var taskIdEl = document.getElementById('progress-task-id');
            var statusEl = document.getElementById('progress-status');
            var stageEl = document.getElementById('progress-stage');
            var barEl = document.getElementById('progress-bar-fill');
            var pctEl = document.getElementById('progress-percentage');
            var fileEl = document.getElementById('progress-current-file');

            if (taskIdEl) taskIdEl.textContent = data.task_id || '-';
            if (statusEl) {
                statusEl.textContent = data.status || '-';
                statusEl.className = 'badge badge-' + (data.status || 'pending');
            }
            if (stageEl) stageEl.textContent = (data.progress && data.progress.stage) || '-';
            if (barEl) {
                var pct = (data.progress && data.progress.percentage) || 0;
                barEl.style.width = pct + '%';
            }
            if (pctEl) {
                pctEl.textContent = ((data.progress && data.progress.percentage) || 0) + '%';
            }
            if (fileEl) fileEl.textContent = (data.progress && data.progress.current_file) || '';
        },

        showProgressPanel: function (taskId) {
            var panel = document.getElementById('scan-progress-panel');
            var taskListPanel = document.getElementById('scan-task-list-panel');
            if (panel) panel.style.display = 'block';
            if (taskListPanel) taskListPanel.style.display = 'block';
            var taskIdEl = document.getElementById('progress-task-id');
            if (taskIdEl) taskIdEl.textContent = taskId;
        },

        hideProgressPanel: function () {
            var panel = document.getElementById('scan-progress-panel');
            if (panel) panel.style.display = 'none';
        },

        stopTask: async function () {
            var taskId = App.state.currentScanPollingId;
            if (!taskId) {
                var currentTasks = Object.keys(App.state.activeScanTasks);
                for (var i = 0; i < currentTasks.length; i++) {
                    var t = App.state.activeScanTasks[currentTasks[i]];
                    if (t.status === 'running' || t.status === 'pending') {
                        taskId = currentTasks[i];
                        break;
                    }
                }
            }
            if (!taskId) {
                App.utils.showToast('没有正在运行的任务', 'warning');
                return;
            }

            try {
                await App.utils.apiRequest(App.apiBase + '/scan/stop/' + taskId, {
                    method: 'POST'
                });
                App.utils.showToast('已请求停止任务: ' + taskId, 'info');
                this.stopPolling();
            } catch (err) {
                App.utils.showToast('停止任务失败: ' + err.message, 'error');
            }
        },

        loadTasks: async function () {
            try {
                var tasks = await App.utils.apiRequest(App.apiBase + '/scan/tasks');
                this.renderTasks(tasks);
            } catch (err) {
                App.utils.showToast('加载任务列表失败: ' + err.message, 'error');
            }
        },

        renderTasks: function (tasks) {
            var tbody = document.getElementById('scan-tasks-body');
            var emptyRow = document.getElementById('scan-tasks-empty');
            if (!tbody) return;

            if (!tasks || tasks.length === 0) {
                tbody.innerHTML = '';
                if (emptyRow) emptyRow.style.display = '';
                return;
            }

            if (emptyRow) emptyRow.style.display = 'none';

            var html = '';
            tasks.forEach(function (task) {
                var statusClass = 'badge badge-' + task.status;
                var statusText = task.status;
                switch (task.status) {
                    case 'completed': statusText = '已完成'; break;
                    case 'running': statusText = '运行中'; break;
                    case 'pending': statusText = '等待中'; break;
                    case 'failed': statusText = '失败'; break;
                    case 'stopped': statusText = '已停止'; break;
                }

                html += '<tr data-task-id="' + App.utils.escapeHtml(task.task_id) + '">';
                html += '<td><code>' + App.utils.escapeHtml(task.task_id) + '</code></td>';
                html += '<td><span class="' + statusClass + '">' + statusText + '</span></td>';
                html += '<td title="' + App.utils.escapeHtml(task.directory || '') + '">' + App.utils.escapeHtml((task.directory || '').length > 40 ? '...' + (task.directory || '').slice(-37) : (task.directory || '')) + '</td>';
                html += '<td>' + (task.file_count || 0) + '</td>';
                html += '<td>' + App.utils.formatDate(task.started_at) + '</td>';
                html += '<td>' + App.utils.formatDate(task.completed_at) + '</td>';
                html += '<td>';
                html += '<button class="btn btn-sm btn-outline view-result-btn" data-task-id="' + App.utils.escapeHtml(task.task_id) + '" title="查看结果">📋</button>';
                if (task.status === 'running' || task.status === 'pending') {
                    html += '<button class="btn btn-sm btn-outline stop-task-btn" data-task-id="' + App.utils.escapeHtml(task.task_id) + '" title="停止任务">⏹</button>';
                }
                html += '</td>';
                html += '</tr>';
            });

            tbody.innerHTML = html;

            var self = this;
            tbody.querySelectorAll('.view-result-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tid = this.getAttribute('data-task-id');
                    App.state.selectedResultTaskId = tid;
                    App.tabs.switchTab('results');
                });
            });
            tbody.querySelectorAll('.stop-task-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tid = this.getAttribute('data-task-id');
                    App.state.currentScanPollingId = tid;
                    self.stopTask();
                });
            });
        },

        clearFinishedTasks: async function () {
            var confirmed = await App.utils.confirmDialog('确定要清除所有已完成的扫描任务记录吗？');
            if (!confirmed) return;

            try {
                var tasks = await App.utils.apiRequest(App.apiBase + '/scan/tasks');
                var finishedTasks = tasks.filter(function (t) {
                    return t.status === 'completed' || t.status === 'failed' || t.status === 'stopped';
                });
                for (var i = 0; i < finishedTasks.length; i++) {
                    try {
                        await App.utils.apiRequest(App.apiBase + '/history/' + finishedTasks[i].task_id, {
                            method: 'DELETE'
                        });
                    } catch (e) { }
                }
                App.utils.showToast('已清除 ' + finishedTasks.length + ' 条记录', 'success');
                this.loadTasks();
            } catch (err) {
                App.utils.showToast('清除失败: ' + err.message, 'error');
            }
        }
    },

    results: {
        init: function () {
            var self = this;
            var selector = document.getElementById('result-task-select');
            if (selector) {
                selector.addEventListener('change', function () {
                    var taskId = this.value;
                    if (taskId) {
                        App.state.selectedResultTaskId = taskId;
                        self.loadResults(taskId);
                    }
                });
            }

            var globalDedupBtn = document.getElementById('btn-global-dedup');
            if (globalDedupBtn) {
                globalDedupBtn.addEventListener('click', function () {
                    if (App.state.selectedResultTaskId) {
                        App.state.currentTaskId = App.state.selectedResultTaskId;
                        App.tabs.switchTab('dedup');
                    } else {
                        App.utils.showToast('请先选择扫描任务', 'warning');
                    }
                });
            }

            var collapseAllBtn = document.getElementById('btn-collapse-all');
            if (collapseAllBtn) {
                collapseAllBtn.addEventListener('click', function () {
                    self.toggleAllGroups(false);
                });
            }

            var expandAllBtn = document.getElementById('btn-expand-all');
            if (expandAllBtn) {
                expandAllBtn.addEventListener('click', function () {
                    self.toggleAllGroups(true);
                });
            }
        },

        loadTaskSelector: async function () {
            var selector = document.getElementById('result-task-select');
            if (!selector) return;

            try {
                var tasks = await App.utils.apiRequest(App.apiBase + '/scan/tasks');
                var completedTasks = tasks.filter(function (t) {
                    return t.status === 'completed';
                });

                var html = '<option value="">-- 选择扫描任务 --</option>';
                completedTasks.forEach(function (task) {
                    var selected = (App.state.selectedResultTaskId === task.task_id) ? ' selected' : '';
                    html += '<option value="' + App.utils.escapeHtml(task.task_id) + '"' + selected + '>' +
                        App.utils.escapeHtml(task.task_id) + ' - ' +
                        App.utils.escapeHtml((task.directory || '').length > 50 ? '...' + (task.directory || '').slice(-47) : (task.directory || '')) +
                        '</option>';
                });
                selector.innerHTML = html;

                if (App.state.selectedResultTaskId) {
                    selector.value = App.state.selectedResultTaskId;
                    this.loadResults(App.state.selectedResultTaskId);
                }
            } catch (err) {
                App.utils.showToast('加载任务列表失败: ' + err.message, 'error');
            }
        },

        loadResults: async function (taskId) {
            if (!taskId) return;

            var container = document.getElementById('results-container');
            if (container) {
                container.innerHTML = '<div style="text-align:center;padding:40px;color:#999;">加载中...</div>';
            }

            try {
                var data = await App.utils.apiRequest(App.apiBase + '/scan/result/' + taskId);
                App.state.selectedResultTaskId = taskId;
                this.renderResults(data);
            } catch (err) {
                if (container) {
                    container.innerHTML = '<div style="text-align:center;padding:40px;color:#F44336;">加载结果失败: ' +
                        App.utils.escapeHtml(err.message) + '</div>';
                }
                App.utils.showToast('加载扫描结果失败: ' + err.message, 'error');
            }
        },

        renderResults: function (data) {
            var container = document.getElementById('results-container');
            if (!container) return;

            var summary = data.summary || {};
            var dupGroups = data.dup_groups || [];
            var sharedFolder = data.shared_folder || '';

            var totalFiles = summary.total_files || 0;
            var totalGroups = summary.total_groups || 0;
            var totalDuplicates = summary.total_duplicates || 0;
            var savable = Math.max(0, totalDuplicates - totalGroups);

            var html = '';

            html += '<div class="summary-cards">';
            html += '<div class="summary-card"><div class="summary-card-value">' + totalFiles + '</div><div class="summary-card-label">总文件数</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + totalGroups + '</div><div class="summary-card-label">重复组数</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + totalDuplicates + '</div><div class="summary-card-label">重复文件数</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + savable + '</div><div class="summary-card-label">可清理文件</div></div>';
            html += '</div>';

            if (dupGroups.length === 0) {
                html += '<div style="text-align:center;padding:40px;color:#4CAF50;font-size:16px;">未发现重复文件</div>';
            } else {
                html += '<div class="dup-groups-container">';
                html += '<div style="margin-bottom:12px;font-weight:600;">共 ' + dupGroups.length + ' 个重复组</div>';

                dupGroups.forEach(function (group, idx) {
                    var groupId = 'dup-group-' + group.group_id;
                    var fileCount = group.files ? group.files.length : 0;
                    var totalSize = 0;
                    if (group.files) {
                        group.files.forEach(function (f) { totalSize += (f.size || 0); });
                    }
                    var wasteSize = totalSize - (group.files && group.files[0] ? (group.files[0].size || 0) : 0);

                    html += '<div class="dup-group-card" id="' + groupId + '">';
                    html += '<div class="dup-group-header" onclick="App.results.toggleGroup(\'' + groupId + '\')">';
                    html += '<span class="group-expand-icon">▶</span>';
                    html += '<span class="group-title">组 #' + group.group_id + '</span>';
                    html += '<span class="group-info">' + fileCount + ' 个文件 | 总大小: ' + App.utils.formatBytes(totalSize) + ' | 可节省: ' + App.utils.formatBytes(wasteSize) + '</span>';
                    html += '<span class="group-md5" title="' + App.utils.escapeHtml(group.md5 || '') + '">MD5: ' + App.utils.escapeHtml((group.md5 || '').substring(0, 8)) + '...</span>';
                    html += '<button class="btn btn-sm btn-primary dedup-group-btn" data-group-id="' + group.group_id + '" onclick="event.stopPropagation();App.results.dedupThisGroup(\'' + group.group_id + '\')">去重</button>';
                    html += '</div>';
                    html += '<div class="dup-group-body" style="display:none;">';
                    html += '<table class="data-table">';
                    html += '<thead><tr><th>文件名</th><th>路径</th><th>大小</th><th>修改时间</th></tr></thead>';
                    html += '<tbody>';

                    if (group.files) {
                        group.files.forEach(function (file) {
                            html += '<tr>';
                            html += '<td><strong>' + App.utils.escapeHtml(file.filename || '') + '</strong></td>';
                            html += '<td title="' + App.utils.escapeHtml(file.path || '') + '">' + App.utils.escapeHtml((file.path || '').length > 60 ? '...' + (file.path || '').slice(-57) : (file.path || '')) + '</td>';
                            html += '<td>' + App.utils.formatBytes(file.size) + '</td>';
                            html += '<td>' + App.utils.formatDate(file.mtime) + '</td>';
                            html += '</tr>';
                        });
                    }

                    html += '</tbody></table>';
                    html += '</div>';
                    html += '</div>';
                });
                html += '</div>';
            }

            container.innerHTML = html;
        },

        toggleGroup: function (groupId) {
            var card = document.getElementById(groupId);
            if (!card) return;
            var body = card.querySelector('.dup-group-body');
            var icon = card.querySelector('.group-expand-icon');
            if (!body || !icon) return;

            if (body.style.display === 'none') {
                body.style.display = 'block';
                icon.textContent = '▼';
            } else {
                body.style.display = 'none';
                icon.textContent = '▶';
            }
        },

        toggleAllGroups: function (expand) {
            var bodies = document.querySelectorAll('.dup-group-body');
            var icons = document.querySelectorAll('.group-expand-icon');
            bodies.forEach(function (body) {
                body.style.display = expand ? 'block' : 'none';
            });
            icons.forEach(function (icon) {
                icon.textContent = expand ? '▼' : '▶';
            });
        },

        dedupThisGroup: function (groupId) {
            App.state.currentTaskId = App.state.selectedResultTaskId;
            App.tabs.switchTab('dedup');
        }
    },

    dedup: {
        init: function () {
            var self = this;

            var taskSelect = document.getElementById('dedup-task-select');
            if (taskSelect) {
                taskSelect.addEventListener('change', function () {
                    App.state.currentTaskId = this.value;
                });
            }

            var modeSelect = document.getElementById('dedup-mode-select');
            if (modeSelect) {
                modeSelect.addEventListener('change', function () {
                    var patternGroup = document.getElementById('dedup-path-pattern-group');
                    if (patternGroup) {
                        patternGroup.style.display = (this.value === 'keep_by_path_pattern') ? 'block' : 'none';
                    }
                });
            }

            var analyzeBtn = document.getElementById('btn-dedup-analyze');
            if (analyzeBtn) {
                analyzeBtn.addEventListener('click', function () { self.analyze(); });
            }

            var previewBtn = document.getElementById('btn-dedup-preview');
            if (previewBtn) {
                previewBtn.addEventListener('click', function () { self.preview(); });
            }

            var generateBtn = document.getElementById('btn-generate-script');
            if (generateBtn) {
                generateBtn.addEventListener('click', function () { self.generateScript(); });
            }

            var saveScriptBtn = document.getElementById('btn-save-script');
            if (saveScriptBtn) {
                saveScriptBtn.addEventListener('click', function () { self.saveScript(); });
            }

            var executeBtn = document.getElementById('btn-execute-dedup');
            if (executeBtn) {
                executeBtn.addEventListener('click', function () { self.executeDedup(); });
            }
        },

        loadDedupTaskSelector: async function () {
            var selector = document.getElementById('dedup-task-select');
            if (!selector) return;

            try {
                var tasks = await App.utils.apiRequest(App.apiBase + '/scan/tasks');
                var completedTasks = tasks.filter(function (t) {
                    return t.status === 'completed';
                });

                var html = '<option value="">-- 选择扫描任务 --</option>';
                completedTasks.forEach(function (task) {
                    var selected = (App.state.currentTaskId === task.task_id) ? ' selected' : '';
                    html += '<option value="' + App.utils.escapeHtml(task.task_id) + '"' + selected + '>' +
                        App.utils.escapeHtml(task.task_id) + ' - ' +
                        App.utils.escapeHtml((task.directory || '').length > 50 ? '...' + (task.directory || '').slice(-47) : (task.directory || '')) +
                        '</option>';
                });
                selector.innerHTML = html;

                if (App.state.currentTaskId) {
                    selector.value = App.state.currentTaskId;
                }
            } catch (err) {
                App.utils.showToast('加载任务列表失败: ' + err.message, 'error');
            }
        },

        getDedupFormData: function () {
            var taskSelect = document.getElementById('dedup-task-select');
            var modeSelect = document.getElementById('dedup-mode-select');
            var patternInput = document.getElementById('dedup-path-pattern');
            var stagingInput = document.getElementById('dedup-staging-dir');
            var reportInput = document.getElementById('dedup-report-file');

            var taskId = taskSelect ? taskSelect.value : '';
            var mode = modeSelect ? modeSelect.value : 'keep_best';
            var pathPattern = null;
            if (mode === 'keep_by_path_pattern') {
                pathPattern = patternInput ? patternInput.value.trim() : '';
            }
            var stagingDir = stagingInput ? stagingInput.value.trim() : '';
            var reportFile = reportInput ? reportInput.value.trim() : '';

            return {
                scan_task_id: taskId,
                mode: mode,
                path_pattern: pathPattern,
                staging_dir: stagingDir || undefined,
                report_file: reportFile || undefined
            };
        },

        analyze: async function () {
            var formData = this.getDedupFormData();
            if (!formData.scan_task_id) {
                App.utils.showToast('请选择扫描任务', 'warning');
                return;
            }

            var btn = document.getElementById('btn-dedup-analyze');
            var container = document.getElementById('dedup-analysis-container');
            App.utils.toggleLoading(btn, true);
            if (container) container.innerHTML = '<div style="text-align:center;padding:20px;color:#999;">分析中...</div>';

            try {
                var body = { scan_task_id: formData.scan_task_id, mode: formData.mode };
                if (formData.path_pattern) body.path_pattern = formData.path_pattern;
                var data = await App.utils.apiRequest(App.apiBase + '/dedup/analyze', {
                    method: 'POST',
                    body: JSON.stringify(body)
                });
                App.state.dedupAnalysisResults = data;
                this.renderAnalysisResults(data);
                App.utils.showToast('分析完成', 'success');
            } catch (err) {
                if (container) container.innerHTML = '<div style="text-align:center;padding:20px;color:#F44336;">分析失败: ' + App.utils.escapeHtml(err.message) + '</div>';
                App.utils.showToast('分析失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        renderAnalysisResults: function (data) {
            var container = document.getElementById('dedup-analysis-container');
            if (!container) return;

            var summary = data.summary || {};
            var analysis = data.analysis || [];

            var html = '';
            html += '<div class="analysis-summary" style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">';
            html += '<div class="summary-card"><div class="summary-card-value">' + (summary.total_groups || 0) + '</div><div class="summary-card-label">总组数</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + (summary.total_remove_files || 0) + '</div><div class="summary-card-label">可移除</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + (summary.total_protected_files || 0) + '</div><div class="summary-card-label">受保护</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + (summary.total_keep_files || 0) + '</div><div class="summary-card-label">保留</div></div>';
            html += '<div class="summary-card"><div class="summary-card-value">' + (summary.office_temp_files || 0) + '</div><div class="summary-card-label">临时文件</div></div>';
            html += '</div>';

            if (summary.category_stats && Object.keys(summary.category_stats).length > 0) {
                html += '<div style="margin-bottom:16px;"><strong>保护分类统计：</strong>';
                var catParts = [];
                Object.keys(summary.category_stats).forEach(function (cat) {
                    catParts.push(App.utils.escapeHtml(cat) + ': ' + summary.category_stats[cat]);
                });
                html += catParts.join(' | ');
                html += '</div>';
            }

            if (analysis.length > 0) {
                html += '<div style="font-weight:600;margin-bottom:8px;">逐组分析结果 (<span id="analysis-group-count">' + analysis.length + '</span> 组)</div>';
                html += '<div class="analysis-groups" style="max-height:500px;overflow-y:auto;">';
                analysis.forEach(function (r) {
                    html += '<div class="analysis-group-item" style="border:1px solid #e0e0e0;border-radius:6px;padding:12px;margin-bottom:8px;">';
                    html += '<div style="font-weight:600;margin-bottom:6px;">组 #' + r.group_id;
                    if (r.office_temp_cleanup) {
                        html += ' <span class="badge badge-warning">Office临时文件</span>';
                    }
                    html += '</div>';

                    if (r.keep) {
                        html += '<div style="margin-bottom:4px;"><span style="color:#4CAF50;">★ 保留:</span> ' +
                            App.utils.escapeHtml(r.keep.path || '') + ' <span style="color:#999;">(' + App.utils.formatBytes(r.keep.size) + ')</span></div>';
                    }

                    if (r.remove && r.remove.length > 0) {
                        html += '<div style="margin-bottom:4px;"><span style="color:#F44336;">✗ 移除 (' + r.remove.length + '个):</span></div>';
                        html += '<ul style="margin:4px 0;padding-left:20px;">';
                        r.remove.forEach(function (f) {
                            html += '<li>' + App.utils.escapeHtml(f.path || '') + ' <span style="color:#999;">(' + App.utils.formatBytes(f.size) + ')</span></li>';
                        });
                        html += '</ul>';
                    }

                    if (r.protected && r.protected.length > 0) {
                        html += '<div style="margin-bottom:4px;"><span style="color:#FF9800;">🛡 受保护 (' + r.protected.length + '个):</span></div>';
                        html += '<ul style="margin:4px 0;padding-left:20px;">';
                        r.protected.forEach(function (f) {
                            html += '<li>' + App.utils.escapeHtml(f.path || '') + ' <span style="color:#999;">(' + App.utils.escapeHtml(f.protect_category || '') + ')</span></li>';
                        });
                        html += '</ul>';
                    }

                    if (!r.keep && !r.remove && r.protected && r.protected.length > 0) {
                        html += '<div style="color:#999;">全部文件受保护，跳过此组</div>';
                    }

                    html += '</div>';
                });
                html += '</div>';
            } else {
                html += '<div style="text-align:center;padding:20px;color:#999;">暂无分析结果</div>';
            }

            container.innerHTML = html;
        },

        preview: async function () {
            var formData = this.getDedupFormData();
            if (!formData.scan_task_id) {
                App.utils.showToast('请选择扫描任务', 'warning');
                return;
            }

            var btn = document.getElementById('btn-dedup-preview');
            var container = document.getElementById('dedup-preview-container');
            App.utils.toggleLoading(btn, true);
            if (container) container.innerHTML = '<div style="text-align:center;padding:20px;color:#999;">生成预览中...</div>';

            try {
                var body = { scan_task_id: formData.scan_task_id, mode: formData.mode };
                if (formData.path_pattern) body.path_pattern = formData.path_pattern;
                var data = await App.utils.apiRequest(App.apiBase + '/dedup/preview', {
                    method: 'POST',
                    body: JSON.stringify(body)
                });
                App.state.dedupPreviewResults = data;
                this.renderPreviewResults(data);
                App.utils.showToast('预览生成完成', 'success');
            } catch (err) {
                if (container) container.innerHTML = '<div style="text-align:center;padding:20px;color:#F44336;">预览失败: ' + App.utils.escapeHtml(err.message) + '</div>';
                App.utils.showToast('预览失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        renderPreviewResults: function (data) {
            var container = document.getElementById('dedup-preview-container');
            if (!container) return;

            var summary = data.summary || {};
            var preview = data.preview || [];

            var html = '';
            html += '<div style="margin-bottom:12px;font-weight:600;">模式: ' + App.utils.escapeHtml(data.mode || '') +
                ' | 可移除: ' + (summary.total_remove_files || 0) + ' 个文件 | 受保护: ' + (summary.total_protected_files || 0) + ' 个文件</div>';

            if (preview.length > 0) {
                html += '<table class="data-table">';
                html += '<thead><tr><th>组ID</th><th>操作</th><th>文件路径</th><th>大小</th><th>类型</th></tr></thead>';
                html += '<tbody>';
                preview.forEach(function (group) {
                    if (group.keep) {
                        html += '<tr style="background:#f1f8e9;">';
                        html += '<td>' + group.group_id + '</td>';
                        html += '<td><span style="color:#4CAF50;">保留</span></td>';
                        html += '<td title="' + App.utils.escapeHtml(group.keep.path || '') + '">' + App.utils.escapeHtmlTruncate(group.keep.path || '', 50) + '</td>';
                        html += '<td>' + App.utils.formatBytes(group.keep.size) + '</td>';
                        html += '<td>-</td>';
                        html += '</tr>';
                    }
                    (group.remove || []).forEach(function (f) {
                        html += '<tr style="background:#fff3f3;">';
                        html += '<td>' + group.group_id + '</td>';
                        html += '<td><span style="color:#F44336;">移除</span></td>';
                        html += '<td title="' + App.utils.escapeHtml(f.path || '') + '">' + App.utils.escapeHtmlTruncate(f.path || '', 50) + '</td>';
                        html += '<td>' + App.utils.formatBytes(f.size) + '</td>';
                        html += '<td>' + (group.office_temp_cleanup ? '临时文件' : '重复文件') + '</td>';
                        html += '</tr>';
                    });
                    (group.protected || []).forEach(function (f) {
                        html += '<tr style="background:#fff8e1;">';
                        html += '<td>' + group.group_id + '</td>';
                        html += '<td><span style="color:#FF9800;">保护</span></td>';
                        html += '<td title="' + App.utils.escapeHtml(f.path || '') + '">' + App.utils.escapeHtmlTruncate(f.path || '', 50) + '</td>';
                        html += '<td>' + App.utils.formatBytes(f.size) + '</td>';
                        html += '<td>' + App.utils.escapeHtml(f.protect_category || '') + '</td>';
                        html += '</tr>';
                    });
                });
                html += '</tbody></table>';
            } else {
                html += '<div style="text-align:center;padding:20px;color:#999;">暂无预览数据</div>';
            }

            container.innerHTML = html;
        },

        generateScript: async function () {
            var formData = this.getDedupFormData();
            if (!formData.scan_task_id) {
                App.utils.showToast('请选择扫描任务', 'warning');
                return;
            }

            var btn = document.getElementById('btn-generate-script');
            App.utils.toggleLoading(btn, true);

            try {
                var body = {
                    scan_task_id: formData.scan_task_id,
                    mode: formData.mode
                };
                if (formData.path_pattern) body.path_pattern = formData.path_pattern;
                if (formData.staging_dir) body.staging_dir = formData.staging_dir;
                if (formData.report_file) body.report_file = formData.report_file;

                var scriptTypeSelect = document.getElementById('dedup-script-type');
                if (scriptTypeSelect && scriptTypeSelect.value) {
                    body.script_type = scriptTypeSelect.value;
                }

                var data = await App.utils.apiRequest(App.apiBase + '/dedup/generate-script', {
                    method: 'POST',
                    body: JSON.stringify(body)
                });

                App.state.generatedScript = data.script;
                App.state.generatedScriptType = data.script_type;

                var textarea = document.getElementById('dedup-script-textarea');
                if (textarea) {
                    textarea.value = data.script;
                }
                var scriptTypeDisplay = document.getElementById('dedup-script-type-display');
                if (scriptTypeDisplay) {
                    scriptTypeDisplay.textContent = data.script_type.toUpperCase();
                }
                var reportDisplay = document.getElementById('dedup-report-display');
                if (reportDisplay) {
                    reportDisplay.textContent = data.report || '';
                }

                App.utils.showToast('脚本生成完成（' + data.script_type.toUpperCase() + '）', 'success');
                App.utils.scrollToElement('dedup-script-section');
            } catch (err) {
                App.utils.showToast('生成脚本失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        saveScript: async function () {
            var script = App.state.generatedScript;
            if (!script) {
                script = (document.getElementById('dedup-script-textarea') || {}).value;
            }
            if (!script) {
                App.utils.showToast('请先生成脚本', 'warning');
                return;
            }

            var scriptType = App.state.generatedScriptType || 'bat';
            var outputPath = prompt('请输入保存路径:', 'dedup_script.' + scriptType);
            if (!outputPath) return;

            var btn = document.getElementById('btn-save-script');
            App.utils.toggleLoading(btn, true);

            try {
                await App.utils.apiRequest(App.apiBase + '/dedup/save-script', {
                    method: 'POST',
                    body: JSON.stringify({
                        script: script,
                        script_type: scriptType,
                        output_path: outputPath
                    })
                });
                App.utils.showToast('脚本已保存: ' + outputPath, 'success');
            } catch (err) {
                App.utils.showToast('保存脚本失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        executeDedup: async function () {
            var formData = this.getDedupFormData();
            if (!formData.scan_task_id) {
                App.utils.showToast('请选择扫描任务', 'warning');
                return;
            }

            var confirmed = await App.utils.confirmDialog(
                '确定要执行去重操作吗？\n\n此操作将把重复文件移动到暂存目录。' +
                '\n受保护的文件将被跳过。\n\n建议先使用"预览"功能确认操作内容。'
            );
            if (!confirmed) return;

            var btn = document.getElementById('btn-execute-dedup');
            var resultContainer = document.getElementById('dedup-execute-result');
            App.utils.toggleLoading(btn, true);

            try {
                var body = {
                    scan_task_id: formData.scan_task_id,
                    mode: formData.mode
                };
                if (formData.path_pattern) body.path_pattern = formData.path_pattern;
                if (formData.staging_dir) body.staging_dir = formData.staging_dir;

                var data = await App.utils.apiRequest(App.apiBase + '/dedup/execute', {
                    method: 'POST',
                    body: JSON.stringify(body)
                });

                if (resultContainer) {
                    var html = '<div style="padding:16px;border-radius:6px;background:#f5f5f5;">';
                    html += '<h4>执行结果</h4>';
                    html += '<p><strong>状态:</strong> <span style="color:#4CAF50;">成功</span></p>';
                    html += '<p><strong>已移动:</strong> ' + (data.moved_count || 0) + ' 个文件</p>';
                    html += '<p><strong>已跳过:</strong> ' + (data.skipped_count || 0) + ' 个文件</p>';
                    html += '<p><strong>失败:</strong> ' + (data.failed_count || 0) + ' 个文件</p>';
                    html += '<p><strong>暂存目录:</strong> ' + App.utils.escapeHtml(data.staging_dir || '') + '</p>';
                    html += '</div>';
                    resultContainer.innerHTML = html;
                }

                App.utils.showToast('去重执行完成！已移动 ' + (data.moved_count || 0) + ' 个文件', 'success');
            } catch (err) {
                if (resultContainer) {
                    resultContainer.innerHTML = '<div style="padding:16px;color:#F44336;">执行失败: ' + App.utils.escapeHtml(err.message) + '</div>';
                }
                App.utils.showToast('执行去重失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        }
    },

    patterns: {
        init: function () {
            var self = this;

            var addForm = document.getElementById('pattern-add-form');
            if (addForm) {
                addForm.addEventListener('submit', function (e) {
                    e.preventDefault();
                    self.addPattern();
                });
            }

            var validateBtn = document.getElementById('btn-validate-regex');
            if (validateBtn) {
                validateBtn.addEventListener('click', function () {
                    self.validateRegexField();
                });
            }

            var testBtn = document.getElementById('btn-test-match');
            if (testBtn) {
                testBtn.addEventListener('click', function () {
                    self.testPathMatch();
                });
            }

            var reloadBtn = document.getElementById('btn-reload-patterns');
            if (reloadBtn) {
                reloadBtn.addEventListener('click', function () {
                    self.loadPatterns();
                });
            }

            var saveBtn = document.getElementById('btn-save-patterns');
            if (saveBtn) {
                saveBtn.addEventListener('click', function () {
                    App.utils.showToast('模式修改会自动保存', 'info');
                    self.loadPatterns();
                });
            }

            var patternRegexInput = document.getElementById('pattern-regex');
            if (patternRegexInput) {
                patternRegexInput.addEventListener('input', function () {
                    self.onPatternRegexInput(this.value);
                });
            }
        },

        loadPatterns: async function () {
            var tbody = document.getElementById('patterns-tbody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:#999;">加载中...</td></tr>';
            }

            try {
                var data = await App.utils.apiRequest(App.apiBase + '/patterns');
                App.state.patternList = data.patterns || [];
                this.renderPatterns(data.patterns || []);
            } catch (err) {
                App.utils.showToast('加载模式列表失败: ' + err.message, 'error');
                if (tbody) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#F44336;">加载失败: ' + App.utils.escapeHtml(err.message) + '</td></tr>';
                }
            }
        },

        renderPatterns: function (patterns) {
            var tbody = document.getElementById('patterns-tbody');
            var emptyRow = document.getElementById('patterns-empty');
            var totalDisplay = document.getElementById('patterns-total');

            if (totalDisplay) totalDisplay.textContent = patterns.length;

            if (!tbody) return;

            if (!patterns || patterns.length === 0) {
                tbody.innerHTML = '';
                if (emptyRow) emptyRow.style.display = '';
                return;
            }

            if (emptyRow) emptyRow.style.display = 'none';

            var html = '';
            patterns.forEach(function (p, idx) {
                html += '<tr data-pattern-index="' + idx + '" class="' + (p.enabled ? '' : 'pattern-disabled') + '">';
                html += '<td>' + (idx + 1) + '</td>';
                html += '<td><code>' + App.utils.escapeHtml(p.pattern || '') + '</code></td>';
                html += '<td>' + App.utils.escapeHtml(p.name || '') + '</td>';
                html += '<td>';
                html += '<label class="toggle-switch">';
                html += '<input type="checkbox" class="pattern-toggle" data-index="' + idx + '" ' + (p.enabled ? 'checked' : '') + '>';
                html += '<span class="toggle-slider"></span>';
                html += '</label>';
                html += '</td>';
                html += '<td>';
                html += '<button class="btn btn-sm btn-outline edit-pattern-btn" data-index="' + idx + '" title="编辑">✏</button>';
                html += '<button class="btn btn-sm btn-outline move-up-btn" data-index="' + idx + '" title="上移" ' + (idx === 0 ? 'disabled' : '') + '>▲</button>';
                html += '<button class="btn btn-sm btn-outline move-down-btn" data-index="' + idx + '" title="下移" ' + (idx === patterns.length - 1 ? 'disabled' : '') + '>▼</button>';
                html += '<button class="btn btn-sm btn-outline delete-pattern-btn" data-index="' + idx + '" title="删除">🗑</button>';
                html += '</td>';
                html += '</tr>';
            });

            tbody.innerHTML = html;

            var self = this;
            tbody.querySelectorAll('.pattern-toggle').forEach(function (cb) {
                cb.addEventListener('change', function () {
                    var idx = parseInt(this.getAttribute('data-index'), 10);
                    self.togglePattern(idx, this.checked);
                });
            });
            tbody.querySelectorAll('.edit-pattern-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var idx = parseInt(this.getAttribute('data-index'), 10);
                    self.showEditForm(idx);
                });
            });
            tbody.querySelectorAll('.move-up-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var idx = parseInt(this.getAttribute('data-index'), 10);
                    self.movePattern(idx, idx - 1);
                });
            });
            tbody.querySelectorAll('.move-down-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var idx = parseInt(this.getAttribute('data-index'), 10);
                    self.movePattern(idx, idx + 1);
                });
            });
            tbody.querySelectorAll('.delete-pattern-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var idx = parseInt(this.getAttribute('data-index'), 10);
                    self.deletePattern(idx);
                });
            });
        },

        validateRegexField: function () {
            var input = document.getElementById('pattern-regex');
            var resultEl = document.getElementById('pattern-regex-validation');
            if (!input || !resultEl) return;

            var patternStr = input.value.trim();
            if (!patternStr) {
                resultEl.innerHTML = '<span style="color:#999;">请输入正则表达式</span>';
                return;
            }

            try {
                new RegExp(patternStr);
                resultEl.innerHTML = '<span style="color:#4CAF50;">✓ 正则表达式有效</span>';
            } catch (e) {
                resultEl.innerHTML = '<span style="color:#F44336;">✗ 无效: ' + App.utils.escapeHtml(e.message) + '</span>';
            }
        },

        onPatternRegexInput: function (value) {
            var resultEl = document.getElementById('pattern-regex-validation');
            if (!resultEl) return;

            if (!value || !value.trim()) {
                resultEl.innerHTML = '';
                return;
            }

            try {
                new RegExp(value.trim());
                resultEl.innerHTML = '<span style="color:#4CAF50;">✓ 有效</span>';
            } catch (e) {
                resultEl.innerHTML = '<span style="color:#F44336;">✗ ' + App.utils.escapeHtml(e.message) + '</span>';
            }
        },

        addPattern: async function () {
            var patternInput = document.getElementById('pattern-regex');
            var nameInput = document.getElementById('pattern-name');
            var enabledInput = document.getElementById('pattern-enabled');

            var patternStr = patternInput ? patternInput.value.trim() : '';
            var name = nameInput ? nameInput.value.trim() : '';
            var enabled = enabledInput ? enabledInput.checked : true;

            if (!patternStr) {
                App.utils.showToast('请输入正则表达式', 'warning');
                return;
            }
            if (!name) {
                App.utils.showToast('请输入模式名称', 'warning');
                return;
            }

            try {
                new RegExp(patternStr);
            } catch (e) {
                App.utils.showToast('正则表达式无效: ' + e.message, 'error');
                return;
            }

            var btn = document.querySelector('#pattern-add-form button[type="submit"]');
            App.utils.toggleLoading(btn, true);

            try {
                await App.utils.apiRequest(App.apiBase + '/patterns', {
                    method: 'POST',
                    body: JSON.stringify({
                        pattern: patternStr,
                        name: name,
                        enabled: enabled
                    })
                });

                if (patternInput) patternInput.value = '';
                if (nameInput) nameInput.value = '';
                var resultEl = document.getElementById('pattern-regex-validation');
                if (resultEl) resultEl.innerHTML = '';

                App.utils.showToast('模式已添加', 'success');
                this.loadPatterns();
            } catch (err) {
                App.utils.showToast('添加模式失败: ' + err.message, 'error');
            } finally {
                App.utils.toggleLoading(btn, false);
            }
        },

        togglePattern: async function (index, enabled) {
            var pattern = App.state.patternList[index];
            if (!pattern) return;

            try {
                await App.utils.apiRequest(App.apiBase + '/patterns/' + index, {
                    method: 'PUT',
                    body: JSON.stringify({
                        pattern: pattern.pattern,
                        name: pattern.name,
                        enabled: enabled
                    })
                });
                App.state.patternList[index].enabled = enabled;
                this.loadPatterns();
            } catch (err) {
                App.utils.showToast('更新失败: ' + err.message, 'error');
                this.loadPatterns();
            }
        },

        showEditForm: function (index) {
            var pattern = App.state.patternList[index];
            if (!pattern) return;

            var formContent = document.createElement('div');
            formContent.innerHTML =
                '<div style="margin-bottom:12px;">' +
                '<label style="display:block;margin-bottom:4px;font-weight:600;">正则表达式:</label>' +
                '<input type="text" id="edit-pattern-regex" value="' + App.utils.escapeHtml(pattern.pattern || '') + '" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;box-sizing:border-box;">' +
                '</div>' +
                '<div style="margin-bottom:12px;">' +
                '<label style="display:block;margin-bottom:4px;font-weight:600;">名称:</label>' +
                '<input type="text" id="edit-pattern-name" value="' + App.utils.escapeHtml(pattern.name || '') + '" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;box-sizing:border-box;">' +
                '</div>' +
                '<div style="margin-bottom:12px;">' +
                '<label><input type="checkbox" id="edit-pattern-enabled" ' + (pattern.enabled ? 'checked' : '') + '> 启用</label>' +
                '</div>';

            var self = this;
            App.utils.showModal('编辑模式 #' + (index + 1), formContent, [
                {
                    text: '取消',
                    callback: function () { }
                },
                {
                    text: '保存',
                    primary: true,
                    callback: function () {
                        var newPattern = document.getElementById('edit-pattern-regex');
                        var newName = document.getElementById('edit-pattern-name');
                        var newEnabled = document.getElementById('edit-pattern-enabled');
                        self.editPattern(index,
                            newPattern ? newPattern.value.trim() : '',
                            newName ? newName.value.trim() : '',
                            newEnabled ? newEnabled.checked : true
                        );
                    }
                }
            ]);
        },

        editPattern: async function (index, patternStr, name, enabled) {
            if (!patternStr) {
                App.utils.showToast('正则表达式不能为空', 'warning');
                return;
            }
            try {
                new RegExp(patternStr);
            } catch (e) {
                App.utils.showToast('正则表达式无效: ' + e.message, 'error');
                return;
            }

            try {
                await App.utils.apiRequest(App.apiBase + '/patterns/' + index, {
                    method: 'PUT',
                    body: JSON.stringify({
                        pattern: patternStr,
                        name: name,
                        enabled: enabled
                    })
                });
                App.utils.showToast('模式已更新', 'success');
                this.loadPatterns();
            } catch (err) {
                App.utils.showToast('更新失败: ' + err.message, 'error');
            }
        },

        deletePattern: async function (index) {
            var pattern = App.state.patternList[index];
            var name = pattern ? pattern.name : ('#' + (index + 1));
            var confirmed = await App.utils.confirmDialog('确定要删除模式 "' + name + '" 吗？');
            if (!confirmed) return;

            try {
                await App.utils.apiRequest(App.apiBase + '/patterns/' + index, {
                    method: 'DELETE'
                });
                App.utils.showToast('模式已删除', 'success');
                this.loadPatterns();
            } catch (err) {
                App.utils.showToast('删除失败: ' + err.message, 'error');
            }
        },

        movePattern: async function (fromIndex, toIndex) {
            if (fromIndex === toIndex) return;

            try {
                await App.utils.apiRequest(App.apiBase + '/patterns/move', {
                    method: 'POST',
                    body: JSON.stringify({
                        from_index: fromIndex,
                        to_index: toIndex
                    })
                });
                this.loadPatterns();
            } catch (err) {
                App.utils.showToast('移动失败: ' + err.message, 'error');
            }
        },

        testPathMatch: async function () {
            var pathInput = document.getElementById('pattern-test-path');
            var resultContainer = document.getElementById('pattern-test-result');
            var path = pathInput ? pathInput.value.trim() : '';

            if (!path) {
                App.utils.showToast('请输入测试路径', 'warning');
                return;
            }

            if (!resultContainer) return;
            resultContainer.innerHTML = '<div style="padding:12px;color:#999;">检测中...</div>';

            try {
                var data = await App.utils.apiRequest(App.apiBase + '/patterns/test', {
                    method: 'POST',
                    body: JSON.stringify({ path: path })
                });

                this.renderTestResult(data, resultContainer);
            } catch (err) {
                resultContainer.innerHTML = '<div style="padding:12px;color:#F44336;">检测失败: ' + App.utils.escapeHtml(err.message) + '</div>';
            }
        },

        renderTestResult: function (data, container) {
            var html = '';
            html += '<div style="padding:12px;">';
            html += '<p><strong>测试路径:</strong> ' + App.utils.escapeHtml(data.path) + '</p>';

            if (data.is_protected) {
                html += '<p><strong>结果:</strong> <span style="color:#FF9800;font-weight:600;">🛡 受保护</span></p>';
                html += '<p><strong>保护类别:</strong> ' + App.utils.escapeHtml(data.protect_category || '') + '</p>';
            } else {
                html += '<p><strong>结果:</strong> <span style="color:#4CAF50;font-weight:600;">✓ 不受保护</span></p>';
            }

            if (data.matches && data.matches.length > 0) {
                html += '<p><strong>匹配的模式:</strong></p>';
                html += '<ul style="margin:4px 0;padding-left:20px;">';
                data.matches.forEach(function (m) {
                    html += '<li><code>' + App.utils.escapeHtml(m.pattern) + '</code> - ' + App.utils.escapeHtml(m.name) + '</li>';
                });
                html += '</ul>';
            } else if (data.is_protected) {
                html += '<p style="color:#999;">（匹配的是全局通用保护规则）</p>';
            } else {
                html += '<p style="color:#999;">无匹配的模式</p>';
            }

            html += '</div>';
            container.innerHTML = html;
        }
    },

    history: {
        init: function () {
            var self = this;

            var statusFilter = document.getElementById('history-status-filter');
            if (statusFilter) {
                statusFilter.addEventListener('change', function () {
                    App.state.historyStatusFilter = this.value;
                    App.state.historyPage = 1;
                    self.loadHistory();
                });
            }

            var prevBtn = document.getElementById('btn-history-prev');
            if (prevBtn) {
                prevBtn.addEventListener('click', function () {
                    if (App.state.historyPage > 1) {
                        App.state.historyPage--;
                        self.loadHistory();
                    }
                });
            }

            var nextBtn = document.getElementById('btn-history-next');
            if (nextBtn) {
                nextBtn.addEventListener('click', function () {
                    App.state.historyPage++;
                    self.loadHistory();
                });
            }

            var refreshBtn = document.getElementById('btn-history-refresh');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', function () {
                    self.loadHistory();
                });
            }

            var statsBtn = document.getElementById('btn-history-stats');
            if (statsBtn) {
                statsBtn.addEventListener('click', function () {
                    self.loadHistoryStats();
                });
            }
        },

        loadHistory: async function () {
            var tbody = document.getElementById('history-tbody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:#999;">加载中...</td></tr>';
            }

            try {
                var data = await App.utils.apiRequest(App.apiBase + '/history');
                var allHistory = data.history || [];

                var filter = App.state.historyStatusFilter;
                if (filter && filter !== 'all') {
                    allHistory = allHistory.filter(function (h) {
                        return h.status === filter;
                    });
                }

                var totalRecords = allHistory.length;
                var totalPages = Math.ceil(totalRecords / App.state.historyPageSize);
                if (App.state.historyPage > totalPages) {
                    App.state.historyPage = Math.max(1, totalPages);
                }

                var start = (App.state.historyPage - 1) * App.state.historyPageSize;
                var pageItems = allHistory.slice(start, start + App.state.historyPageSize);

                this.renderHistory(pageItems, totalRecords, totalPages);
            } catch (err) {
                App.utils.showToast('加载历史记录失败: ' + err.message, 'error');
                if (tbody) {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#F44336;">加载失败: ' + App.utils.escapeHtml(err.message) + '</td></tr>';
                }
            }
        },

        renderHistory: function (items, totalRecords, totalPages) {
            var tbody = document.getElementById('history-tbody');
            var emptyRow = document.getElementById('history-empty');
            var pageInfo = document.getElementById('history-page-info');
            var prevBtn = document.getElementById('btn-history-prev');
            var nextBtn = document.getElementById('btn-history-next');
            var totalDisplay = document.getElementById('history-total-display');

            if (!tbody) return;

            if (totalDisplay) totalDisplay.textContent = totalRecords;

            if (!items || items.length === 0) {
                tbody.innerHTML = '';
                if (emptyRow) emptyRow.style.display = '';
                if (pageInfo) pageInfo.textContent = '0 / 0 页';
                if (prevBtn) prevBtn.disabled = true;
                if (nextBtn) nextBtn.disabled = true;
                return;
            }

            if (emptyRow) emptyRow.style.display = 'none';

            var html = '';
            items.forEach(function (h) {
                var statusClass = 'badge badge-' + (h.status || 'unknown');
                var statusText = h.status || '';
                switch (h.status) {
                    case 'completed': statusText = '已完成'; break;
                    case 'running': statusText = '运行中'; break;
                    case 'pending': statusText = '等待中'; break;
                    case 'failed': statusText = '失败'; break;
                    case 'stopped': statusText = '已停止'; break;
                }

                html += '<tr data-task-id="' + App.utils.escapeHtml(h.task_id) + '">';
                html += '<td>' + App.utils.escapeHtml(h.task_id) + '</td>';
                html += '<td><span class="' + statusClass + '">' + statusText + '</span></td>';
                html += '<td title="' + App.utils.escapeHtml(h.directory || '') + '">' + App.utils.escapeHtmlTruncate(h.directory || '', 40) + '</td>';
                html += '<td>' + (h.file_count || 0) + '</td>';
                html += '<td>' + App.utils.formatDate(h.started_at) + '</td>';
                html += '<td>' + App.utils.formatDate(h.completed_at) + '</td>';
                html += '<td>' + App.utils.escapeHtmlTruncate(h.error || '', 30) + '</td>';
                html += '<td>';
                html += '<button class="btn btn-sm btn-outline history-view-btn" data-task-id="' + App.utils.escapeHtml(h.task_id) + '" title="查看详情">📋</button>';
                html += '<button class="btn btn-sm btn-outline history-export-btn" data-task-id="' + App.utils.escapeHtml(h.task_id) + '" title="导出">📥</button>';
                html += '<button class="btn btn-sm btn-outline history-delete-btn" data-task-id="' + App.utils.escapeHtml(h.task_id) + '" title="删除">🗑</button>';
                html += '</td>';
                html += '</tr>';
            });

            tbody.innerHTML = html;

            if (pageInfo) {
                pageInfo.textContent = App.state.historyPage + ' / ' + totalPages + ' 页（共 ' + totalRecords + ' 条）';
            }
            if (prevBtn) prevBtn.disabled = App.state.historyPage <= 1;
            if (nextBtn) nextBtn.disabled = App.state.historyPage >= totalPages;

            var self = this;
            tbody.querySelectorAll('.history-view-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tid = this.getAttribute('data-task-id');
                    self.viewDetail(tid);
                });
            });
            tbody.querySelectorAll('.history-export-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tid = this.getAttribute('data-task-id');
                    self.exportRecord(tid);
                });
            });
            tbody.querySelectorAll('.history-delete-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var tid = this.getAttribute('data-task-id');
                    self.deleteRecord(tid);
                });
            });
        },

        viewDetail: async function (taskId) {
            try {
                var data = await App.utils.apiRequest(App.apiBase + '/history/' + taskId);

                var content = '<div style="font-size:14px;line-height:1.8;">';
                content += '<p><strong>任务ID:</strong> ' + App.utils.escapeHtml(data.task_id) + '</p>';
                content += '<p><strong>状态:</strong> ' + App.utils.escapeHtml(data.status) + '</p>';
                content += '<p><strong>扫描目录:</strong> ' + App.utils.escapeHtml(data.directory || '') + '</p>';
                content += '<p><strong>文件总数:</strong> ' + (data.file_count || 0) + '</p>';
                content += '<p><strong>开始时间:</strong> ' + App.utils.formatDate(data.started_at) + '</p>';
                content += '<p><strong>完成时间:</strong> ' + App.utils.formatDate(data.completed_at) + '</p>';
                if (data.error) {
                    content += '<p><strong>错误信息:</strong> <span style="color:#F44336;">' + App.utils.escapeHtml(data.error) + '</span></p>';
                }
                if (data.stats) {
                    content += '<p><strong>重复组数:</strong> ' + (data.stats.duplicate_groups || 0) + '</p>';
                    content += '<p><strong>重复文件数:</strong> ' + (data.stats.duplicate_files || 0) + '</p>';
                }
                content += '</div>';

                App.utils.showModal('历史记录详情', content, [
                    { text: '关闭', callback: function () { } }
                ]);
            } catch (err) {
                App.utils.showToast('加载详情失败: ' + err.message, 'error');
            }
        },

        exportRecord: async function (taskId) {
            try {
                var data = await App.utils.apiRequest(App.apiBase + '/scan/result/' + taskId);

                var lines = [];
                lines.push('=== 去重扫描结果报告 ===');
                lines.push('任务ID: ' + taskId);
                lines.push('扫描目录: ' + (data.shared_folder || ''));
                lines.push('生成时间: ' + new Date().toISOString());
                lines.push('');

                var summary = data.summary || {};
                lines.push('--- 汇总 ---');
                lines.push('总文件数: ' + (summary.total_files || 0));
                lines.push('重复组数: ' + (summary.total_groups || 0));
                lines.push('重复文件数: ' + (summary.total_duplicates || 0));
                lines.push('');

                var groups = data.dup_groups || [];
                groups.forEach(function (g) {
                    lines.push('--- 组 #' + g.group_id + ' ---');
                    lines.push('MD5: ' + (g.md5 || ''));
                    (g.files || []).forEach(function (f) {
                        lines.push('  ' + f.path + ' (' + App.utils.formatBytes(f.size) + ', ' + (f.mtime || '') + ')');
                    });
                    lines.push('');
                });

                var blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/plain;charset=utf-8' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'dedup_report_' + taskId + '.txt';
                a.click();
                URL.revokeObjectURL(url);

                App.utils.showToast('报告已导出', 'success');
            } catch (err) {
                App.utils.showToast('导出失败: ' + err.message, 'error');
            }
        },

        deleteRecord: async function (taskId) {
            var confirmed = await App.utils.confirmDialog('确定要删除历史记录 ' + taskId + ' 吗？此操作不可撤销。');
            if (!confirmed) return;

            try {
                await App.utils.apiRequest(App.apiBase + '/history/' + taskId, {
                    method: 'DELETE'
                });
                App.utils.showToast('历史记录已删除', 'success');
                this.loadHistory();
            } catch (err) {
                App.utils.showToast('删除失败: ' + err.message, 'error');
            }
        },

        loadHistoryStats: async function () {
            try {
                var data = await App.utils.apiRequest(App.apiBase + '/history');
                var history = data.history || [];

                var counts = { completed: 0, running: 0, pending: 0, failed: 0, stopped: 0 };
                var totalFiles = 0;
                history.forEach(function (h) {
                    if (counts.hasOwnProperty(h.status)) {
                        counts[h.status]++;
                    }
                    totalFiles += (h.file_count || 0);
                });

                var content = '<div style="font-size:14px;line-height:1.8;">';
                content += '<p><strong>总记录数:</strong> ' + history.length + '</p>';
                content += '<p><strong>已完成:</strong> ' + counts.completed + '</p>';
                content += '<p><strong>运行中:</strong> ' + counts.running + '</p>';
                content += '<p><strong>等待中:</strong> ' + counts.pending + '</p>';
                content += '<p><strong>失败:</strong> ' + counts.failed + '</p>';
                content += '<p><strong>已停止:</strong> ' + counts.stopped + '</p>';
                content += '<p><strong>累计扫描文件:</strong> ' + totalFiles + '</p>';
                content += '</div>';

                App.utils.showModal('历史统计', content, [
                    { text: '关闭', callback: function () { } }
                ]);
            } catch (err) {
                App.utils.showToast('加载统计数据失败: ' + err.message, 'error');
            }
        }
    },

    init: function () {
        this.tabs.init();
        this.scan.init();
        this.results.init();
        this.dedup.init();
        this.patterns.init();
        this.history.init();

        this.injectStyles();
        this.tabs.switchTab(this.state.currentTab);

        App.utils.showToast('文件去重工具已就绪', 'info');

        if (this.state.taskRefreshTimer) {
            clearInterval(this.state.taskRefreshTimer);
        }
        this.state.taskRefreshTimer = setInterval(function () {
            if (App.state.currentTab === 'scan') {
                App.scan.loadTasks();
            }
        }, 10000);
    },

    injectStyles: function () {
        if (document.getElementById('app-dynamic-styles')) return;

        var style = document.createElement('style');
        style.id = 'app-dynamic-styles';
        style.textContent = '@keyframes slideInRight{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}';
        document.head.appendChild(style);
    }
};

document.addEventListener('DOMContentLoaded', function () {
    App.init();
});
