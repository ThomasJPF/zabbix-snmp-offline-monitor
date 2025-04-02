<?php
declare(strict_types = 1);

namespace Modules\SNMPMonitor\Widgets\SNMPMonitorGraphWidget;

use Zabbix\Core\CWidget;
use Zabbix\Widgets\CWidgetField;
use Zabbix\Widgets\Fields\CWidgetFieldMultiSelectGroup;

use API;
use CApiInputValidator;
use CWebUser;
use CControllerResponseData;
use CRoleHelper;

use Modules\SNMPMonitor\Includes\SNMPHelper;

/**
 * SNMP Status Graph widget.
 */
class Widget extends CWidget {
    /**
     * Widget: Initialize form fields.
     */
    public function getForm(): array {
        return [
            'fields' => [
                (new CWidgetFieldMultiSelectGroup('groupids', _('Host groups')))
                    ->setFlags(CWidgetField::FLAG_NOT_EMPTY)
            ]
        ];
    }

    /**
     * Widget: Default configuration.
     */
    public function getDefaultName(): string {
        return _('SNMP Status Graph');
    }

    /**
     * Widget: Validate form fields.
     */
    public function validate(array $fields): array {
        $errors = parent::validate($fields);

        if (!array_key_exists('groupids', $errors)) {
            $groupids = array_key_exists('groupids', $fields) ? $fields['groupids'] : [];

            if ($groupids) {
                // Check if all specified host groups exist and are accessible.
                $db_groups = API::HostGroup()->get([
                    'output' => [],
                    'groupids' => $groupids,
                    'preservekeys' => true
                ]);

                $inaccessible_groupids = array_diff($groupids, array_keys($db_groups));

                if ($inaccessible_groupids) {
                    $errors['groupids'] = _('No permissions to referred object or it does not exist!');
                }
            }
        }

        return $errors;
    }

    /**
     * Widget: Execute.
     */
    public function execute(array $options): CControllerResponseData {
        // Verifica permissões
        if (!CWebUser::checkAccess(CRoleHelper::ACTIONS_MONITOR_PROBLEMS)) {
            return $this->getResponse(WIDGET_SNMPGRAPH_VIEW, [
                'error' => _('No permissions to view SNMP status')
            ]);
        }

        $groupids = $options['groupids'] ?? [];
        
        // Obtém hosts com interfaces SNMP
        $hosts = SNMPHelper::getSNMPHosts($groupids);
        
        // Obtém estatísticas
        $stats = SNMPHelper::getSNMPStats($hosts);
        
        // Dados para o gráfico
        $chart_data = [
            ['value' => $stats['online'], 'label' => _('Online'), 'color' => '#76c576'],
            ['value' => $stats['offline'] - $stats['ping_only'], 'label' => _('Completely Offline'), 'color' => '#e45959'],
            ['value' => $stats['ping_only'], 'label' => _('Ping Only'), 'color' => '#ffb64f'],
            ['value' => $stats['unknown'], 'label' => _('Unknown'), 'color' => '#ababab']
        ];
        
        return $this->getResponse(WIDGET_SNMPGRAPH_VIEW, [
            'name' => $this->getDefaultName(),
            'stats' => $stats,
            'chart_data' => $chart_data
        ]);
    }
} 