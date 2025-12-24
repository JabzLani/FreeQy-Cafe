// Dashboard JavaScript for real-time updates

class CafeDashboard {
    constructor() {
        this.socket = io();
        this.clients = {};
        this.setupSocketEvents();
        this.setupEventListeners();
        this.initCharts();
        this.loadInitialData();
    }

    setupSocketEvents() {
        // Client connection events
        this.socket.on('client_connected', (data) => {
            this.showAlert(`Client ${data.pi_id} connected`, 'success');
            this.loadClients();
        });

        this.socket.on('client_disconnected', (data) => {
            this.showAlert(`Client ${data.pi_id} disconnected`, 'warning');
            this.loadClients();
        });

        // Resource updates
        this.socket.on('resource_update', (data) => {
            this.updateClientResources(data.pi_id, data.resources);
            this.updateClientCard(data.pi_id);
        });

        // Initial connection
        this.socket.on('connect', () => {
            console.log('Connected to monitoring server');
        });
    }

    setupEventListeners() {
        // Refresh clients
        document.getElementById('refresh-clients').addEventListener('click', () => {
            this.loadClients();
            this.loadSessions();
            this.loadStats();
        });

        // Start session
        document.getElementById('start-session').addEventListener('click', () => {
            this.startSession();
        });

        // End session
        document.getElementById('end-session').addEventListener('click', () => {
            this.endSession();
        });

        // Client select change
        document.getElementById('client-select').addEventListener('change', (e) => {
            const clientId = e.target.value;
            if (clientId) {
                this.showClientDetails(clientId);
            }
        });
    }

    async loadInitialData() {
        await Promise.all([
            this.loadClients(),
            this.loadSessions(),
            this.loadStats()
        ]);
    }

    async loadClients() {
        try {
            const response = await fetch('/api/clients');
            const data = await response.json();
            this.clients = {};

            const container = document.getElementById('clients-container');
            const select = document.getElementById('client-select');

            // Clear existing options except the first
            while (select.options.length > 1) {
                select.remove(1);
            }

            container.innerHTML = '';

            data.clients.forEach(client => {
                this.clients[client.pi_id] = client;
                this.createClientCard(client);

                // Add to select dropdown
                const option = document.createElement('option');
                option.value = client.pi_id;
                option.textContent = `${client.hostname} (${client.pi_id.substring(0, 8)}...)`;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading clients:', error);
        }
    }

    async loadSessions() {
        try {
            const response = await fetch('/api/sessions/today');
            const data = await response.json();
            const table = document.getElementById('sessions-table');

            table.innerHTML = '';

            data.sessions.forEach(session => {
                const row = document.createElement('tr');

                const duration = session.duration
                    ? this.formatDuration(session.duration)
                    : 'Active';

                const cost = session.cost
                    ? `$${session.cost.toFixed(2)}`
                    : '-';

                row.innerHTML = `
                    <td>${session.pi_id.substring(0, 8)}...</td>
                    <td>${session.user_name}</td>
                    <td>${duration}</td>
                    <td>${cost}</td>
                `;

                table.appendChild(row);
            });
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();

            document.getElementById('online-count').textContent = data.online_clients;
            document.getElementById('active-sessions').textContent = data.active_sessions;
            document.getElementById('today-revenue').textContent = data.today_revenue.toFixed(2);
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    createClientCard(client) {
        const container = document.getElementById('clients-container');

        const card = document.createElement('div');
        card.className = 'col-md-6 col-lg-4';
        card.id = `client-${client.pi_id}`;

        const statusClass = client.status === 'online' ? 'status-online' : 'status-offline';
        const statusIcon = client.status === 'online' ? 'bi-check-circle' : 'bi-x-circle';

        card.innerHTML = `
            <div class="card client-card" data-client-id="${client.pi_id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="card-title mb-1">
                                <i class="bi bi-pc"></i> ${client.hostname}
                            </h6>
                            <p class="text-muted small mb-2">
                                ${client.pi_id.substring(0, 12)}...
                            </p>
                        </div>
                        <div class="${statusClass}">
                            <i class="bi ${statusIcon}"></i>
                            <small>${client.status}</small>
                        </div>
                    </div>
                    
                    <div class="row mt-2">
                        <div class="col-6">
                            <small class="text-muted">CPU</small>
                            <div class="progress cpu-gauge">
                                <div class="progress-bar bg-danger" style="width: 0%"></div>
                            </div>
                        </div>
                        <div class="col-6">
                            <small class="text-muted">Memory</small>
                            <div class="progress memory-gauge">
                                <div class="progress-bar bg-info" style="width: 0%"></div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row mt-2">
                        <div class="col-6">
                            <small class="text-muted">Last Seen</small>
                            <div class="small">${new Date(client.last_seen).toLocaleTimeString()}</div>
                        </div>
                        <div class="col-6">
                            <button class="btn btn-sm btn-outline-primary w-100" onclick="dashboard.showClientDetails('${client.pi_id}')">
                                Details
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.appendChild(card);
    }

    updateClientResources(clientId, resources) {
        if (!this.clients[clientId]) {
            this.clients[clientId] = { resources: {} };
        }
        this.clients[clientId].resources = resources;
        this.clients[clientId].last_seen = new Date().toISOString();
    }

    updateClientCard(clientId) {
        const client = this.clients[clientId];
        if (!client || !client.resources) return;

        const card = document.querySelector(`#client-${clientId} .client-card`);
        if (!card) return;

        // Update CPU and memory bars
        const cpuBar = card.querySelector('.cpu-gauge .progress-bar');
        const memoryBar = card.querySelector('.memory-gauge .progress-bar');

        if (cpuBar && client.resources.cpu_percent) {
            cpuBar.style.width = `${Math.min(client.resources.cpu_percent, 100)}%`;
            cpuBar.innerHTML = `<span>${client.resources.cpu_percent}%</span>`;
        }

        if (memoryBar && client.resources.memory_percent) {
            memoryBar.style.width = `${Math.min(client.resources.memory_percent, 100)}%`;
            memoryBar.innerHTML = `<span>${client.resources.memory_percent}%</span>`;
        }

        // Update status
        const statusDiv = card.querySelector('.status-online, .status-offline');
        if (statusDiv) {
            statusDiv.className = 'status-online';
            statusDiv.innerHTML = '<i class="bi bi-check-circle"></i> <small>online</small>';
        }
    }

    async startSession() {
        const clientId = document.getElementById('client-select').value;
        const userName = document.getElementById('user-name').value || 'Guest';

        if (!clientId) {
            this.showAlert('Please select a client first', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/session/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pi_id: clientId, user_name: userName })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(`Session started for ${userName} on client ${clientId}`, 'success');
                this.loadSessions();
                this.loadStats();
            } else {
                this.showAlert(data.message, 'danger');
            }
        } catch (error) {
            console.error('Error starting session:', error);
            this.showAlert('Failed to start session', 'danger');
        }
    }

    async endSession() {
        const clientId = document.getElementById('client-select').value;

        if (!clientId) {
            this.showAlert('Please select a client first', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/session/end', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pi_id: clientId })
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert(`Session ended. Duration: ${this.formatDuration(data.duration)}, Cost: $${data.cost}`, 'success');
                this.loadSessions();
                this.loadStats();
            } else {
                this.showAlert(data.message, 'danger');
            }
        } catch (error) {
            console.error('Error ending session:', error);
            this.showAlert('Failed to end session', 'danger');
        }
    }

    showClientDetails(clientId) {
        const client = this.clients[clientId];
        if (!client) return;

        // Update modal content
        document.getElementById('detail-hostname').textContent = client.hostname;
        document.getElementById('detail-ip').textContent = client.ip_address || '-';
        document.getElementById('detail-status').textContent = client.status;
        document.getElementById('detail-last-seen').textContent =
            new Date(client.last_seen).toLocaleString();

        if (client.resources) {
            document.getElementById('detail-cpu').textContent = client.resources.cpu_percent || '-';
            document.getElementById('detail-memory').textContent = client.resources.memory_percent || '-';
            document.getElementById('detail-disk').textContent = client.resources.disk_percent || '-';
            document.getElementById('detail-temp').textContent = client.resources.temperature || '-';

            // Update progress bars
            const cpuBar = document.getElementById('detail-cpu-bar');
            const memoryBar = document.getElementById('detail-memory-bar');
            const diskBar = document.getElementById('detail-disk-bar');

            if (cpuBar && client.resources.cpu_percent) {
                cpuBar.style.width = `${Math.min(client.resources.cpu_percent, 100)}%`;
            }
            if (memoryBar && client.resources.memory_percent) {
                memoryBar.style.width = `${Math.min(client.resources.memory_percent, 100)}%`;
            }
            if (diskBar && client.resources.disk_percent) {
                diskBar.style.width = `${Math.min(client.resources.disk_percent, 100)}%`;
            }

            // Update processes table
            const processesTable = document.getElementById('detail-processes').querySelector('tbody');
            processesTable.innerHTML = '';

            if (client.resources.applications) {
                client.resources.applications.forEach(app => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${app.pid}</td>
                        <td>${app.name}</td>
                        <td>${app.cpu || 0}%</td>
                        <td>${app.memory || 0}%</td>
                    `;
                    processesTable.appendChild(row);
                });
            }
        }

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('clientModal'));
        modal.show();
    }

    initCharts() {
        const ctx = document.getElementById('resourceChart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Avg CPU %',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    },
                    {
                        label: 'Avg Memory %',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }

    updateChart() {
        // This would update the chart with aggregated data
        // Implement based on your needs
    }

    showAlert(message, type = 'info') {
        const container = document.getElementById('alerts-container');

        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        container.prepend(alert);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }

    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        }
        return `${minutes}m`;
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new CafeDashboard();
});