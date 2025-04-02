<?php
/**
 * Widget SNMP Status Graph view
 */

// Se houver erro
if (array_key_exists('error', $data)) {
    ?>
    <div class="widget-error">
        <?= $data['error'] ?>
    </div>
    <?php
    return;
}

// Container para o gráfico
$chart_container = (new CDiv())
    ->addClass('snmp-graph-widget')
    ->addStyle('height: 100%; min-height: 230px; position: relative;');

// Informações de estatísticas
$stats = $data['stats'];
$total = $stats['total'];

// HTML para o widget
?>
<div class="dashboard-widget-snmpgraph" style="height: 100%;">
    <?php
    if ($total === 0) {
        ?>
        <div class="no-data" style="display: flex; align-items: center; justify-content: center; height: 100%; color: #888;">
            <?= _('No SNMP devices found') ?>
        </div>
        <?php
    }
    else {
        ?>
        <div class="widget-stats" style="display: flex; justify-content: space-around; margin-bottom: 10px;">
            <div class="stat-item" style="text-align: center;">
                <span class="stat-label" style="font-size: 0.85em; color: #888;"><?= _('Online') ?></span>
                <span class="stat-value" style="display: block; font-size: 1.2em; color: #76c576;"><?= $stats['online'] ?></span>
            </div>
            <div class="stat-item" style="text-align: center;">
                <span class="stat-label" style="font-size: 0.85em; color: #888;"><?= _('Offline') ?></span>
                <span class="stat-value" style="display: block; font-size: 1.2em; color: #e45959;"><?= $stats['offline'] ?></span>
            </div>
            <div class="stat-item" style="text-align: center;">
                <span class="stat-label" style="font-size: 0.85em; color: #888;"><?= _('Ping Only') ?></span>
                <span class="stat-value" style="display: block; font-size: 1.2em; color: #ffb64f;"><?= $stats['ping_only'] ?></span>
            </div>
            <div class="stat-item" style="text-align: center;">
                <span class="stat-label" style="font-size: 0.85em; color: #888;"><?= _('Total') ?></span>
                <span class="stat-value" style="display: block; font-size: 1.2em;"><?= $stats['total'] ?></span>
            </div>
        </div>
        <div id="snmp-graph-container-<?= $data['widgetid'] ?>" style="height: calc(100% - 60px); min-height: 200px;"></div>
        <?php
    }
    ?>
</div>

<script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        const chart_data = <?= json_encode($data['chart_data']) ?>;
        const container = document.getElementById('snmp-graph-container-<?= $data['widgetid'] ?>');
        
        if (!container) return;
        
        const canvas = document.createElement('canvas');
        canvas.width = container.offsetWidth;
        canvas.height = container.offsetHeight;
        container.appendChild(canvas);
        
        if (typeof Chart !== 'undefined') {
            new Chart(canvas, {
                type: 'pie',
                data: {
                    datasets: [{
                        data: chart_data.map(item => item.value),
                        backgroundColor: chart_data.map(item => item.color),
                    }],
                    labels: chart_data.map(item => item.label)
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 12,
                            padding: 10,
                            fontSize: 10
                        }
                    },
                    tooltips: {
                        callbacks: {
                            label: function(tooltipItem, data) {
                                const dataset = data.datasets[tooltipItem.datasetIndex];
                                const value = dataset.data[tooltipItem.index];
                                const total = dataset.data.reduce((acc, val) => acc + val, 0);
                                const percentage = Math.round((value / total) * 100);
                                return data.labels[tooltipItem.index] + ': ' + value + ' (' + percentage + '%)';
                            }
                        }
                    }
                }
            });
        } else {
            // Fallback para quando Chart.js não está disponível
            let fallbackHtml = '<div style="padding: 15px;">';
            let total = chart_data.reduce((acc, val) => acc + val.value, 0);
            
            chart_data.forEach(item => {
                const percent = total > 0 ? Math.round((item.value / total) * 100) : 0;
                fallbackHtml += `<div style="margin-bottom: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; background-color: ${item.color}; margin-right: 5px;"></span>
                    <span>${item.label}: ${item.value} (${percent}%)</span>
                </div>`;
            });
            
            fallbackHtml += '</div>';
            container.innerHTML = fallbackHtml;
        }
    });
</script> 