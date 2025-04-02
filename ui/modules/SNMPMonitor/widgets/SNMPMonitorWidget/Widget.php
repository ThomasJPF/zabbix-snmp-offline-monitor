<?php
declare(strict_types = 1);

namespace Modules\SNMPMonitor\Widgets\SNMPMonitorWidget;

use Zabbix\Core\CWidget;
use Zabbix\Widgets\CWidgetField;
use Zabbix\Widgets\Fields\CWidgetFieldMultiSelectGroup;
use Zabbix\Widgets\Fields\CWidgetFieldCheckBox;
use Zabbix\Widgets\Fields\CWidgetFieldIntegerBox;

use API;
use CApiInputValidator;
use CWebUser;
use CControllerResponseData;
use CRoleHelper;

use Modules\SNMPMonitor\Includes\SNMPHelper;

/**
 * SNMP Offline Devices widget.
 */
class Widget extends CWidget {
    // Definições de constantes para o widget
    const DEFAULT_SHOW_ONLY_OFFLINE = 1;
    const DEFAULT_SHOW_PING_STATUS = 1;
    const DEFAULT_MAX_ITEMS = 10;

    /**
     * Widget: Initialize form fields.
     */
    public function getForm(): array {
        return [
            'fields' => [
                (new CWidgetFieldMultiSelectGroup('groupids', _('Host groups'))),
                (new CWidgetFieldCheckBox('show_only_offline', _('Show only offline devices')))
                    ->setDefault(self::DEFAULT_SHOW_ONLY_OFFLINE),
                (new CWidgetFieldCheckBox('show_ping_status', _('Show ping status')))
                    ->setDefault(self::DEFAULT_SHOW_PING_STATUS),
                (new CWidgetFieldIntegerBox('max_items', _('Max devices'), 1, 100))
                    ->setDefault(self::DEFAULT_MAX_ITEMS)
            ]
        ];
    }

    /**
     * Widget: Default configuration.
     */
    public function getDefaultName(): string {
        return _('SNMP Offline Devices');
    }

    /**
     * Widget: Validate form fields.
     */
    public function validate(array $fields): array {
        $errors = parent::validate($fields);

        if (!array_key_exists('groupids', $errors) && array_key_exists('groupids', $fields)) {
            $groupids = $fields['groupids'];

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
            return $this->getResponse(WIDGET_SNMPMONITOR_VIEW, [
                'error' => _('No permissions to view SNMP status')
            ]);
        }

        $groupids = array_key_exists('groupids', $options) ? $options['groupids'] : [];
        $show_only_offline = array_key_exists('show_only_offline', $options) 
            ? (int) $options['show_only_offline'] 
            : self::DEFAULT_SHOW_ONLY_OFFLINE;
        $show_ping_status = array_key_exists('show_ping_status', $options) 
            ? (int) $options['show_ping_status'] 
            : self::DEFAULT_SHOW_PING_STATUS;
        $max_items = array_key_exists('max_items', $options) 
            ? (int) $options['max_items'] 
            : self::DEFAULT_MAX_ITEMS;
        
        // Obtém hosts com interfaces SNMP
        $hosts = SNMPHelper::getSNMPHosts($groupids);
        
        // Filtra dispositivos offline se necessário
        if ($show_only_offline) {
            $hosts = array_filter($hosts, function($host) {
                return $host['snmp_status']['status'] === 0;
            });
        }
        
        // Limita o número de dispositivos
        $hosts = array_slice($hosts, 0, $max_items);
        
        return $this->getResponse(WIDGET_SNMPMONITOR_VIEW, [
            'name' => $this->getDefaultName(),
            'hosts' => $hosts,
            'show_ping_status' => $show_ping_status,
            'max_items' => $max_items,
            'total_offline' => count(array_filter($hosts, function($host) {
                return $host['snmp_status']['status'] === 0;
            }))
        ]);
    }
} 