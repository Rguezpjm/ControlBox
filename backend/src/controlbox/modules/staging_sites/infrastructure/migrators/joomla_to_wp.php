<?php
/**
 * Joomla to WordPress Migration Script
 * Runs inside the staging WordPress container.
 * Usage: php joomla_to_wp.php <joomla_prefix>
 */

define('WP_USE_THEMES', false);
require_once __DIR__ . '/wp-load.php';

function report_progress($percent, $status) {
    echo json_encode(['percent' => intval($percent), 'status' => $status]) . "\n";
    flush();
}

$joomla_prefix = isset($argv[1]) ? trim($argv[1]) : 'jos_';

global $wpdb;

report_progress(5, "Starting Joomla to WordPress migration...");

// 1. Check if Joomla tables exist in the same database
$tables = $wpdb->get_col("SHOW TABLES LIKE '{$joomla_prefix}%'");
if (empty($tables)) {
    report_progress(100, "Error: No Joomla tables found with prefix '{$joomla_prefix}' in the database.");
    exit(1);
}

// Map category IDs from Joomla to WordPress
$category_mapping = [];

// 2. Migrate Joomla categories to WordPress
report_progress(10, "Migrating core categories...");
$joomla_categories = $wpdb->get_results("SELECT id, title, alias, description FROM {$joomla_prefix}categories WHERE extension = 'com_content'");
foreach ($joomla_categories as $idx => $cat) {
    $term = wp_insert_term($cat->title, 'category', [
        'description' => $cat->description,
        'slug' => $cat->alias
    ]);
    if (!is_wp_error($term)) {
        $category_mapping[$cat->id] = $term['term_id'];
    } else {
        // If term already exists, fetch its ID
        $existing = get_term_by('slug', $cat->alias, 'category');
        if ($existing) {
            $category_mapping[$cat->id] = $existing->term_id;
        }
    }
}

// 3. Migrate Joomla articles to WordPress
report_progress(25, "Migrating core Joomla articles...");
$joomla_articles = $wpdb->get_results("SELECT id, catid, title, alias, introtext, `fulltext`, state, created, created_by_alias FROM {$joomla_prefix}content");
$total_articles = count($joomla_articles);
foreach ($joomla_articles as $idx => $art) {
    $content = $art->introtext . "\n" . $art->fulltext;
    $post_data = [
        'post_title'    => $art->title,
        'post_name'     => $art->alias,
        'post_content'  => $content,
        'post_status'   => ($art->state == 1) ? 'publish' : 'draft',
        'post_date'     => $art->created,
        'post_type'     => 'post',
        'post_category' => isset($category_mapping[$art->catid]) ? [$category_mapping[$art->catid]] : []
    ];
    wp_insert_post($post_data);
    
    if ($idx % 50 === 0 && $total_articles > 0) {
        $progress = 25 + intval(($idx / $total_articles) * 20);
        report_progress($progress, "Migrated {$idx}/{$total_articles} core articles...");
    }
}

// 4. Migrate K2 if tables are present
$has_k2 = in_array("{$joomla_prefix}k2_items", $tables);
if ($has_k2) {
    report_progress(50, "K2 extension detected. Migrating K2 categories and items...");
    
    // Migrate K2 categories
    $k2_categories = $wpdb->get_results("SELECT id, name, alias, description FROM {$joomla_prefix}k2_categories");
    $k2_cat_mapping = [];
    foreach ($k2_categories as $cat) {
        $term = wp_insert_term($cat->name, 'category', [
            'description' => $cat->description,
            'slug' => $cat->alias
        ]);
        if (!is_wp_error($term)) {
            $k2_cat_mapping[$cat->id] = $term['term_id'];
        } else {
            $existing = get_term_by('slug', $cat->alias, 'category');
            if ($existing) {
                $k2_cat_mapping[$cat->id] = $existing->term_id;
            }
        }
    }
    
    // Migrate K2 items
    $k2_items = $wpdb->get_results("SELECT title, alias, catid, introtext, `fulltext`, created, published FROM {$joomla_prefix}k2_items");
    $total_k2 = count($k2_items);
    foreach ($k2_items as $idx => $item) {
        $content = $item->introtext . "\n" . $item->fulltext;
        $post_data = [
            'post_title'    => $item->title,
            'post_name'     => $item->alias,
            'post_content'  => $content,
            'post_status'   => ($item->published == 1) ? 'publish' : 'draft',
            'post_date'     => $item->created,
            'post_type'     => 'post',
            'post_category' => isset($k2_cat_mapping[$item->catid]) ? [$k2_cat_mapping[$item->catid]] : []
        ];
        wp_insert_post($post_data);
        
        if ($idx % 50 === 0 && $total_k2 > 0) {
            $progress = 50 + intval(($idx / $total_k2) * 15);
            report_progress($progress, "Migrated {$idx}/{$total_k2} K2 items...");
        }
    }
}

// 5. Migrate Kunena Forums if tables are present
$has_kunena = in_array("{$joomla_prefix}kunena_messages", $tables);
if ($has_kunena) {
    report_progress(70, "Kunena Forum detected. Migrating forum categories and messages...");
    
    // Create a "Forums" parent category
    $forum_cat = wp_insert_term('Forums', 'category', ['description' => 'Migrated Kunena Forums']);
    $forum_cat_id = !is_wp_error($forum_cat) ? $forum_cat['term_id'] : get_term_by('name', 'Forums', 'category')->term_id;
    
    // Retrieve categories
    $kunena_categories = $wpdb->get_results("SELECT id, name, alias, description FROM {$joomla_prefix}kunena_categories");
    $kunena_cat_mapping = [];
    foreach ($kunena_categories as $cat) {
        $term = wp_insert_term($cat->name, 'category', [
            'description' => $cat->description,
            'slug' => $cat->alias,
            'parent' => $forum_cat_id
        ]);
        if (!is_wp_error($term)) {
            $kunena_cat_mapping[$cat->id] = $term['term_id'];
        } else {
            $existing = get_term_by('slug', $cat->alias, 'category');
            if ($existing) {
                $kunena_cat_mapping[$cat->id] = $existing->term_id;
            }
        }
    }
    
    // Migrate Topics (messages where parent = 0)
    $topics = $wpdb->get_results("SELECT id, catid, name, subject, time FROM {$joomla_prefix}kunena_messages WHERE parent = 0");
    $topic_post_mapping = [];
    foreach ($topics as $topic) {
        // Find main message body from text table if available, or use subject
        $body_table = in_array("{$joomla_prefix}kunena_messages_text", $tables) ? "{$joomla_prefix}kunena_messages_text" : null;
        $body = $topic->subject;
        if ($body_table) {
            $text_row = $wpdb->get_row($wpdb->prepare("SELECT message FROM {$body_table} WHERE mesid = %d", $topic->id));
            if ($text_row) {
                $body = $text_row->message;
            }
        }
        
        $post_data = [
            'post_title'    => $topic->subject,
            'post_content'  => $body,
            'post_status'   => 'publish',
            'post_date'     => date('Y-m-d H:i:s', $topic->time),
            'post_type'     => 'post',
            'post_category' => isset($kunena_cat_mapping[$topic->catid]) ? [$kunena_cat_mapping[$topic->catid]] : [$forum_cat_id]
        ];
        $post_id = wp_insert_post($post_data);
        if ($post_id) {
            $topic_post_mapping[$topic->id] = $post_id;
        }
    }
    
    // Migrate Replies (parent > 0) as comments on the topic post
    $replies = $wpdb->get_results("SELECT id, thread, name, email, subject, time FROM {$joomla_prefix}kunena_messages WHERE parent > 0");
    foreach ($replies as $reply) {
        if (isset($topic_post_mapping[$reply->thread])) {
            $parent_post_id = $topic_post_mapping[$reply->thread];
            $body = $reply->subject;
            $body_table = in_array("{$joomla_prefix}kunena_messages_text", $tables) ? "{$joomla_prefix}kunena_messages_text" : null;
            if ($body_table) {
                $text_row = $wpdb->get_row($wpdb->prepare("SELECT message FROM {$body_table} WHERE mesid = %d", $reply->id));
                if ($text_row) {
                    $body = $text_row->message;
                }
            }
            
            wp_insert_comment([
                'comment_post_ID'      => $parent_post_id,
                'comment_author'       => $reply->name,
                'comment_author_email' => $reply->email,
                'comment_content'      => $body,
                'comment_date'         => date('Y-m-d H:i:s', $reply->time),
                'comment_approved'     => 1,
            ]);
        }
    }
}

// 6. Migrate PhocaDownload if tables are present
$has_phoca = in_array("{$joomla_prefix}phocadownload", $tables);
if ($has_phoca) {
    report_progress(85, "PhocaDownload detected. Migrating download files...");
    
    // Map categories
    $phoca_categories = $wpdb->get_results("SELECT id, title, alias, description FROM {$joomla_prefix}phocadownload_categories");
    $phoca_cat_mapping = [];
    foreach ($phoca_categories as $cat) {
        $term = wp_insert_term($cat->title, 'category', [
            'description' => $cat->description,
            'slug' => $cat->alias
        ]);
        if (!is_wp_error($term)) {
            $phoca_cat_mapping[$cat->id] = $term['term_id'];
        } else {
            $existing = get_term_by('slug', $cat->alias, 'category');
            if ($existing) {
                $phoca_cat_mapping[$cat->id] = $existing->term_id;
            }
        }
    }
    
    // Migrate files as downloadable media attachments or custom post types
    $phoca_files = $wpdb->get_results("SELECT title, alias, filename, catid, description, date FROM {$joomla_prefix}phocadownload");
    foreach ($phoca_files as $file) {
        // Create a standard post for the file link
        $content = "Descargar archivo: <code>" . esc_html($file->filename) . "</code>\n\n" . $file->description;
        $post_data = [
            'post_title'    => $file->title,
            'post_name'     => $file->alias,
            'post_content'  => $content,
            'post_status'   => 'publish',
            'post_date'     => $file->date,
            'post_type'     => 'post',
            'post_category' => isset($phoca_cat_mapping[$file->catid]) ? [$phoca_cat_mapping[$file->catid]] : []
        ];
        wp_insert_post($post_data);
    }
}

// 7. Cleanup Joomla tables
report_progress(95, "Cleaning up database Joomla tables...");
foreach ($tables as $tbl) {
    $wpdb->query("DROP TABLE IF EXISTS {$tbl}");
}

report_progress(100, "Migration completed successfully!");
?>
