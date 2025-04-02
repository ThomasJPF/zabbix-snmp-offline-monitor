<?php

/**
 * Página principal do SNMP Monitor
 */

use Zabbix\Widgets\Fields\CWidgetFieldTextBox;

// Cria a página
$this->addJsFile('js/class.dashboard.widget.js');
$this->addJsFile('js/class.svg.canvas.js');
$this->addJsFile('js/class.svg.map.js');
$this->addJsFile('js/class.calendar.js');

$page_title = _('SNMP Monitor');

$this->data['page']['title'] = $page_title;
$this->data['page']['web_layout_mode'] = 'layout.mode';

// Filtro de grupo de hosts
$filter_form = (new CForm('get'))
    ->setName('snmp-filter-form')
    ->addClass(ZBX_STYLE_FILTER_CONTAINER)
    ->addVar('action', 'snmp.monitor');

// Campo de seleção de grupos
$group_ms = (new CMultiSelect([
    'name' => 'groupids[]',
    'object_name' => 'hostGroup',
    'data' => array_values(array_map(function ($groupid, $group) {
        return [
            'id' => $groupid,
            'name' => $group['name']
        ];
    }, array_keys($data['hostgroups']), $data['hostgroups'])),
    'popup' => [
        'parameters' => [
            'srctbl' => 'host_groups',
            'srcfld1' => 'groupid',
            'dstfrm' => 'snmp-filter-form',
            'dstfld1' => 'groupids_'
        ]
    ],
    'multiple' => true
]))->setWidth(ZBX_TEXTAREA_FILTER_STANDARD_WIDTH);

// Adiciona valores selecionados
if ($data['selected_groups']) {
    $group_ms->setValue($data['selected_groups']);
}

$group_filter = (new CFormList())
    ->addRow(_('Host groups'), $group_ms)
    ->addRow('',
        (new CButton('filter_set', _('Apply')))
            ->onClick('javascript: document.forms["snmp-filter-form"].submit();')
    );

$filter_form->addItem($group_filter);

// Stats container
$stats_container = (new CDiv())
    ->addClass('stats-container')
    ->addStyle('display: flex; gap: 20px; margin-bottom: 20px;');

// Widget de estatísticas
$stats_widget = (new CDiv())
    ->addClass('stats-widget')
    ->addStyle('flex: 1; background-color: #fff; padding: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,.1);');

$stats_title = (new CDiv(_('SNMP Status Overview')))
    ->addClass('stats-title')
    ->addStyle('font-size: 16px; font-weight: bold; margin-bottom: 15px;');

$stats_grid = (new CDiv())
    ->addClass('stats-grid')
    ->addStyle('display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;');

// Boxes de estatísticas
$online_box = (new CDiv())
    ->addClass('stat-box online')
    ->addStyle('padding: 15px; border-radius: 5px; background-color: #d5f3d5; text-align: center;')
    ->addItem([
        (new CSpan(_('Online')))->addClass('stat-label')->addStyle('display: block; font-size: 14px;'),
        (new CSpan($data['stats']['online']))->addClass('stat-value')->addStyle('display: block; font-size: 24px; font-weight: bold;'),
    ]);

$offline_box = (new CDiv())
    ->addClass('stat-box offline')
    ->addStyle('padding: 15px; border-radius: 5px; background-color: #ffb8b8; text-align: center;')
    ->addItem([
        (new CSpan(_('Offline')))->addClass('stat-label')->addStyle('display: block; font-size: 14px;'),
        (new CSpan($data['stats']['offline']))->addClass('stat-value')->addStyle('display: block; font-size: 24px; font-weight: bold;'),
    ]);

$ping_box = (new CDiv())
    ->addClass('stat-box ping')
    ->addStyle('padding: 15px; border-radius: 5px; background-color: #ffecc1; text-align: center;')
    ->addItem([
        (new CSpan(_('Ping Only')))->addClass('stat-label')->addStyle('display: block; font-size: 14px;'),
        (new CSpan($data['stats']['ping_only']))->addClass('stat-value')->addStyle('display: block; font-size: 24px; font-weight: bold;'),
    ]);

$unknown_box = (new CDiv())
    ->addClass('stat-box unknown')
    ->addStyle('padding: 15px; border-radius: 5px; background-color: #e8e8e8; text-align: center;')
    ->addItem([
        (new CSpan(_('Unknown')))->addClass('stat-label')->addStyle('display: block; font-size: 14px;'),
        (new CSpan($data['stats']['unknown']))->addClass('stat-value')->addStyle('display: block; font-size: 24px; font-weight: bold;'),
    ]);

$stats_grid->addItem([$online_box, $offline_box, $ping_box, $unknown_box]);
$stats_widget->addItem([$stats_title, $stats_grid]);

// Gráfico de pizza
$chart_widget = (new CDiv())
    ->addClass('chart-widget')
    ->addStyle('flex: 1; background-color: #fff; padding: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,.1);');

$chart_title = (new CDiv(_('SNMP Status Distribution')))
    ->addClass('chart-title')
    ->addStyle('font-size: 16px; font-weight: bold; margin-bottom: 15px;');

// Dados para o gráfico
$chart_data = [
    ['value' => $data['stats']['online'], 'label' => _('Online'), 'color' => '#76c576'],
    ['value' => $data['stats']['offline'] - $data['stats']['ping_only'], 'label' => _('Completely Offline'), 'color' => '#e45959'],
    ['value' => $data['stats']['ping_only'], 'label' => _('Ping Only'), 'color' => '#ffb64f'],
    ['value' => $data['stats']['unknown'], 'label' => _('Unknown'), 'color' => '#ababab']
];

// Canvas e script para renderizar o gráfico
$chart_container = (new CDiv())
    ->setAttribute('id', 'snmp-chart-container')
    ->addStyle('height: 200px;');

$chart_script = (new CScriptTag('
    document.addEventListener("DOMContentLoaded", function() {
        const data = '.json_encode($chart_data).';
        const ctx = document.createElement("canvas");
        ctx.width = 400;
        ctx.height = 200;
        document.getElementById("snmp-chart-container").appendChild(ctx);
        
        // Verifica se todos os valores são zero
        const allZero = data.every(item => item.value === 0);
        
        if (allZero) {
            const container = document.getElementById("snmp-chart-container");
            container.style.display = "flex";
            container.style.alignItems = "center";
            container.style.justifyContent = "center";
            container.innerHTML = "<div style=\'text-align: center; color: #888;\'>'._('No data to display').'</div>";
            return;
        }
        
        if (typeof Chart !== "undefined") {
            new Chart(ctx, {
                type: "pie",
                data: {
                    datasets: [{
                        data: data.map(item => item.value),
                        backgroundColor: data.map(item => item.color),
                    }],
                    labels: data.map(item => item.label)
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    legend: {
                        position: "right",
                        labels: {
                            boxWidth: 12,
                            padding: 10
                        }
                    },
                    tooltips: {
                        callbacks: {
                            label: function(tooltipItem, data) {
                                const dataset = data.datasets[tooltipItem.datasetIndex];
                                const value = dataset.data[tooltipItem.index];
                                const total = dataset.data.reduce((acc, val) => acc + val, 0);
                                const percentage = Math.round((value / total) * 100);
                                return data.labels[tooltipItem.index] + ": " + value + " (" + percentage + "%)";
                            }
                        }
                    }
                }
            });
        } else {
            // Fallback para quando Chart.js não está disponível
            let fallbackHtml = "<div>";
            data.forEach(item => {
                const percent = Math.round((item.value / data.reduce((acc, val) => acc + val.value, 0)) * 100);
                fallbackHtml += `<div style="margin-bottom: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; background-color: ${item.color}; margin-right: 5px;"></span>
                    <span>${item.label}: ${item.value} (${percent}%)</span>
                </div>`;
            });
            fallbackHtml += "</div>";
            document.getElementById("snmp-chart-container").innerHTML = fallbackHtml;
        }
    });
'))->setType('text/javascript');

$chart_widget->addItem([
    $chart_title,
    $chart_container,
    $chart_script
]);

$stats_container->addItem([$stats_widget, $chart_widget]);

// Tabela de hosts
$host_table = (new CTableInfo())
    ->setHeader([
        _('Host'),
        _('IP'),
        _('SNMP Status'),
        _('Ping Status'),
        _('Last check'),
        _('Error message')
    ]);

foreach ($data['hosts'] as $host) {
    // Status SNMP
    if ($host['snmp_status']['status'] === 1) {
        $snmp_status = (new CSpan(_('Online')))->addClass(ZBX_STYLE_GREEN);
    } 
    elseif ($host['snmp_status']['status'] === 0) {
        $snmp_status = (new CSpan(_('Offline')))->addClass(ZBX_STYLE_RED);
    }
    else {
        $snmp_status = (new CSpan(_('Unknown')))->addClass(ZBX_STYLE_GREY);
    }
    
    // Status Ping
    if ($host['ping_status']['status'] === 1) {
        $ping_status = (new CSpan(_('Online')))->addClass(ZBX_STYLE_GREEN);
    } 
    elseif ($host['ping_status']['status'] === 0) {
        $ping_status = (new CSpan(_('Offline')))->addClass(ZBX_STYLE_RED);
    }
    else {
        $ping_status = (new CSpan(_('Unknown')))->addClass(ZBX_STYLE_GREY);
    }
    
    // Último check
    $last_check = $host['snmp_status']['last_check'] > 0 
        ? date('Y-m-d H:i:s', $host['snmp_status']['last_check'])
        : '-';
        
    // Mensagem de erro
    $error = $host['snmp_status']['error'] ?? '';
    
    $host_table->addRow([
        new CLink($host['name'], 'zabbix.php?action=host.view&hostid='.$host['hostid']),
        $host['snmp_interface']['ip'],
        $snmp_status,
        $ping_status,
        $last_check,
        $error
    ]);
}

// Botões de exportação
$export_buttons = (new CList())
    ->addClass(ZBX_STYLE_BTN_SPLIT)
    ->addItem((new CButton('export', _('Export')))
        ->onClick('javascript: window.location.href = "'.
            (new CUrl('zabbix.php'))
                ->setArgument('action', 'snmp.monitor.download')
                ->setArgument('format', 'csv')
                ->setArgument('groupids', $data['selected_groups'])
                ->getUrl() . 
        '";'
    ))
    ->addItem((new CButton('export-xlsx', _('Export as XLSX')))
        ->onClick('javascript: window.location.href = "'.
            (new CUrl('zabbix.php'))
                ->setArgument('action', 'snmp.monitor.download')
                ->setArgument('format', 'xlsx')
                ->setArgument('groupids', $data['selected_groups'])
                ->getUrl() . 
        '";'
    ));

// Widget container
(new CWidget())
    ->setTitle($page_title)
    ->setRefreshUrl($data['refresh_url'])
    ->setControls(
        (new CTag('nav', true, 
            (new CList())
                ->addItem($export_buttons)
        ))->setAttribute('aria-label', _('Content controls'))
    )
    ->addItem($filter_form)
    ->addItem($stats_container)
    ->addItem($host_table)
    ->show();
    
// Adiciona a biblioteca Chart.js
$this->includeJsFile('js/Chart.bundle.min.js'); 