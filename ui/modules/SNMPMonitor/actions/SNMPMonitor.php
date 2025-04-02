<?php

namespace Modules\SNMPMonitor\Actions;

use CController,
    CControllerResponseData,
    CWebUser,
    CRoleHelper,
    CArrayHelper;

use Modules\SNMPMonitor\Includes\SNMPHelper;

class SNMPMonitor extends CController {
    protected function init(): void {
        $this->disableCsrfValidation();
    }

    protected function checkInput(): bool {
        $fields = [
            'groupids' => 'array_id'
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
        
        // Obtém todos os grupos de host
        $hostgroups = SNMPHelper::getHostGroups();

        // Obtém hosts com interfaces SNMP
        $hosts = SNMPHelper::getSNMPHosts($groupids);

        // Obtém estatísticas
        $stats = SNMPHelper::getSNMPStats($hosts);

        // Prepara os dados para a view
        $data = [
            'hosts' => $hosts,
            'hostgroups' => $hostgroups,
            'stats' => $stats,
            'selected_groups' => $groupids ?: [],
            'refresh_url' => $this->getUrl('snmp.monitor', ['groupids' => $groupids])
        ];

        $response = new CControllerResponseData($data);
        $this->setResponse($response);
    }
} 