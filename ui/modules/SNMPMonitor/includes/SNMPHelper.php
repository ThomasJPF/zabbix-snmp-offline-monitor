<?php

namespace Modules\SNMPMonitor\Includes;

use API;
use CAPIHelper;

class SNMPHelper {
    /**
     * Obtém todos os hosts com interfaces SNMP
     *
     * @param array $hostgroup_ids   IDs dos grupos de host para filtrar (opcional)
     * @return array
     */
    public static function getSNMPHosts($hostgroup_ids = null) {
        $options = [
            'output' => ['hostid', 'host', 'name', 'status'],
            'selectInterfaces' => ['interfaceid', 'ip', 'type', 'main', 'port', 'error'],
            'selectGroups' => ['groupid', 'name'],
            'filter' => ['status' => 0] // Somente hosts ativos
        ];

        if ($hostgroup_ids) {
            $options['groupids'] = $hostgroup_ids;
        }

        $hosts = API::Host()->get($options);
        
        // Filtra hosts com interface SNMP e verifica status SNMP
        $snmp_hosts = [];
        foreach ($hosts as $host) {
            foreach ($host['interfaces'] as $interface) {
                if ($interface['type'] == '2') { // Tipo 2 é SNMP
                    $host['snmp_interface'] = $interface;
                    
                    // Busca item SNMP status
                    $items = API::Item()->get([
                        'hostids' => $host['hostid'],
                        'search' => ['key_' => 'snmp.status'],
                        'output' => ['itemid', 'lastvalue', 'lastclock', 'error']
                    ]);
                    
                    if ($items) {
                        $host['snmp_status'] = [
                            'status' => (int)$items[0]['lastvalue'],
                            'last_check' => $items[0]['lastclock'],
                            'error' => $items[0]['error']
                        ];
                    } else {
                        $host['snmp_status'] = [
                            'status' => -1, // Desconhecido
                            'last_check' => 0,
                            'error' => 'Item SNMP Status não encontrado'
                        ];
                    }
                    
                    // Verifica status de ping
                    $ping_items = API::Item()->get([
                        'hostids' => $host['hostid'],
                        'search' => ['key_' => 'icmpping'},
                        'output' => ['itemid', 'lastvalue', 'lastclock']
                    ]);
                    
                    if ($ping_items) {
                        $host['ping_status'] = [
                            'status' => (int)$ping_items[0]['lastvalue'],
                            'last_check' => $ping_items[0]['lastclock']
                        ];
                    } else {
                        $host['ping_status'] = [
                            'status' => -1, // Desconhecido
                            'last_check' => 0
                        ];
                    }
                    
                    $snmp_hosts[] = $host;
                    break;
                }
            }
        }
        
        return $snmp_hosts;
    }
    
    /**
     * Obtém todos os grupos de host
     *
     * @return array
     */
    public static function getHostGroups() {
        return API::HostGroup()->get([
            'output' => ['groupid', 'name'],
            'preservekeys' => true,
            'sortfield' => 'name'
        ]);
    }
    
    /**
     * Obtém estatísticas de status SNMP
     *
     * @param array $hosts   Lista de hosts com status SNMP
     * @return array
     */
    public static function getSNMPStats($hosts) {
        $stats = [
            'total' => count($hosts),
            'online' => 0,
            'offline' => 0,
            'unknown' => 0,
            'ping_only' => 0
        ];
        
        foreach ($hosts as $host) {
            if ($host['snmp_status']['status'] === 1) {
                $stats['online']++;
            } 
            elseif ($host['snmp_status']['status'] === 0) {
                $stats['offline']++;
                
                // Verifica se responde ping
                if ($host['ping_status']['status'] === 1) {
                    $stats['ping_only']++;
                }
            }
            else {
                $stats['unknown']++;
            }
        }
        
        return $stats;
    }
} 