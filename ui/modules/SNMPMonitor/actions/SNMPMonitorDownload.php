<?php

namespace Modules\SNMPMonitor\Actions;

use CController,
    CControllerResponseData,
    CWebUser,
    CRoleHelper,
    CCsvResponse;

use Modules\SNMPMonitor\Includes\SNMPHelper;

class SNMPMonitorDownload extends CController {
    protected function init(): void {
        $this->disableCsrfValidation();
    }

    protected function checkInput(): bool {
        $fields = [
            'groupids' => 'array_id',
            'format' => 'in csv,xlsx'
        ];

        $ret = $this->validateInput($fields);

        if (!$ret) {
            $this->setResponse(
                (new CControllerResponseData(['main_block' => json_encode([
                    'error' => [
                        'messages' => array_column(get_and_clear_messages(), 'message')
                    ]
                ])]))->disableView()
            );
        }

        return $ret;
    }

    protected function checkPermissions(): bool {
        return CWebUser::checkAccess(CRoleHelper::ACTIONS_MONITOR_PROBLEMS);
    }

    protected function doAction(): void {
        $groupids = $this->hasInput('groupids') ? $this->getInput('groupids') : null;
        $format = $this->hasInput('format') ? $this->getInput('format') : 'csv';
        
        // Obtém hosts com interfaces SNMP
        $hosts = SNMPHelper::getSNMPHosts($groupids);
        
        // Prepara dados para exportação
        $export_data = [];
        
        // Cabeçalho
        $header = [
            _('Hostname'),
            _('IP'),
            _('SNMP Status'),
            _('Ping Status'),
            _('Último check'),
            _('Mensagem de erro')
        ];
        
        $export_data[] = $header;
        
        // Dados dos hosts
        foreach ($hosts as $host) {
            $snmp_status = '';
            switch ($host['snmp_status']['status']) {
                case 1:
                    $snmp_status = _('Online');
                    break;
                case 0:
                    $snmp_status = _('Offline');
                    break;
                default:
                    $snmp_status = _('Desconhecido');
            }
            
            $ping_status = '';
            switch ($host['ping_status']['status']) {
                case 1:
                    $ping_status = _('Online');
                    break;
                case 0:
                    $ping_status = _('Offline');
                    break;
                default:
                    $ping_status = _('Desconhecido');
            }
            
            $last_check = date('Y-m-d H:i:s', $host['snmp_status']['last_check']);
            $error = $host['snmp_status']['error'] ?? '';
            
            $export_data[] = [
                $host['name'],
                $host['snmp_interface']['ip'],
                $snmp_status,
                $ping_status,
                $last_check,
                $error
            ];
        }
        
        // Exporta como CSV ou XLSX
        if ($format === 'csv') {
            $response = new CCsvResponse();
            $response->setName('snmp_monitor_report.csv');
            $response->addRows($export_data);
            $this->setResponse($response);
        }
        else {
            // Para XLSX, usamos a biblioteca PhpSpreadsheet através da classe CXlsxResponse
            $response = new CXlsxResponse();
            $response->setTitle(_('Relatório de Monitoramento SNMP'));
            $response->setName('snmp_monitor_report.xlsx');
            $response->addRows($export_data);
            $this->setResponse($response);
        }
    }
} 