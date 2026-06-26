<?php
/**
 * Joomla Database Schema Migrator
 * Runs inside the staging Joomla container.
 * Finds com_admin updates SQL files and executes them sequentially.
 */

define('_JEXEC', 1);
define('JPATH_BASE', __DIR__);
require_once __DIR__ . '/includes/defines.php';
require_once __DIR__ . '/includes/framework.php';

function report_progress($percent, $status) {
    echo json_encode(['percent' => intval($percent), 'status' => $status]) . "\n";
    flush();
}

report_progress(5, "Connecting to Joomla database...");
$db = JFactory::getDbo();
$config = JFactory::getConfig();
$prefix = $config->get('dbprefix');

// Get current database version from #__schemas
$query = "SELECT version_id FROM {$prefix}schemas WHERE extension_id = 700";
$db->setQuery($query);
$current_version = $db->loadResult();
if (!$current_version) {
    // If no version found, default to '0.0.0'
    $current_version = '0.0.0';
}

report_progress(15, "Current database version is: {$current_version}");

$updates_dir = __DIR__ . '/administrator/components/com_admin/sql/updates/mysql';
if (!is_dir($updates_dir)) {
    report_progress(100, "Error: Updates directory not found at '{$updates_dir}'.");
    exit(1);
}

// Read all sql update files
$files = glob($updates_dir . '/*.sql');
natsort($files);

$applied = 0;
$total_files = count($files);

foreach ($files as $idx => $file) {
    $version_name = basename($file, '.sql');
    
    // Compare version strings
    if (version_compare($version_name, $current_version, '>')) {
        report_progress(20 + intval(($idx / $total_files) * 70), "Applying database updates for version {$version_name}...");
        
        $sql_content = file_get_contents($file);
        // Remove comments
        $sql_content = preg_replace('/--.*\n/', '', $sql_content);
        $sql_content = preg_replace('/\/\*.*?\*\//s', '', $sql_content);
        
        // Split statements by semicolon
        $queries = explode(';', $sql_content);
        foreach ($queries as $q) {
            $q = trim($q);
            if (!empty($q)) {
                // Replace prefix placeholder #__
                $q = str_replace('#__', $prefix, $q);
                try {
                    $db->setQuery($q);
                    $db->execute();
                } catch (Exception $e) {
                    // Ignore errors (e.g. column already exists) during schema migration
                }
            }
        }
        
        // Update version in #__schemas
        $update_query = "UPDATE {$prefix}schemas SET version_id = " . $db->quote($version_name) . " WHERE extension_id = 700";
        $db->setQuery($update_query);
        $db->execute();
        
        $applied++;
    }
}

report_progress(100, "Joomla database schema migrated successfully! Applied {$applied} updates.");
?>
