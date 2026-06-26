<?php
/**
 * Blogger XML Backup Importer
 * Detects whether it is running in WordPress or Joomla, parses the Blogger XML,
 * and imports categories/tags, posts/articles, and comments.
 * Usage: php import_blogger.php <xml_file_path>
 */

function report_progress($percent, $status) {
    echo json_encode(['percent' => intval($percent), 'status' => $status]) . "\n";
    flush();
}

$xml_path = isset($argv[1]) ? trim($argv[1]) : '';
if (empty($xml_path) || !file_exists($xml_path)) {
    report_progress(100, "Error: Blogger XML file not found at '{$xml_path}'.");
    exit(1);
}

report_progress(5, "Reading Blogger backup file...");
$xml_data = file_get_contents($xml_path);
// Disable entity expansion to prevent XXE
libxml_use_internal_errors(true);
$xml = simplexml_load_string($xml_data, 'SimpleXMLElement', LIBXML_NONET);
if (!$xml) {
    report_progress(100, "Error: Invalid Blogger XML backup format.");
    exit(1);
}

// Register namespaces
$namespaces = $xml->getDocNamespaces(true);
$xml->registerXPathNamespace('atom', 'http://www.w3.org/2005/Atom');
$xml->registerXPathNamespace('thr', 'http://schemas.google.com/thr/2007');

// Parse posts and comments
report_progress(15, "Parsing Blogger posts and comments...");

$posts = [];
$comments = [];

foreach ($xml->entry as $entry) {
    $id = (string)$entry->id;
    
    // Determine entry type
    $is_post = false;
    $is_comment = false;
    
    foreach ($entry->category as $cat) {
        $term = (string)$cat['term'];
        if (strpos($term, '#post') !== false) {
            $is_post = true;
        } elseif (strpos($term, '#comment') !== false) {
            $is_comment = true;
        }
    }
    
    if ($is_post) {
        $title = (string)$entry->title;
        $content = (string)$entry->content;
        $published = (string)$entry->published;
        
        // Extract tags
        $tags = [];
        foreach ($entry->category as $cat) {
            $scheme = (string)$cat['scheme'];
            if (strpos($scheme, '/ns#') !== false) {
                $tags[] = (string)$cat['term'];
            }
        }
        
        $posts[$id] = [
            'title' => $title ?: 'Untitled Post',
            'content' => $content,
            'published' => $published,
            'tags' => $tags,
            'wp_post_id' => 0
        ];
    } elseif ($is_comment) {
        $content = (string)$entry->content;
        $published = (string)$entry->published;
        $author_name = isset($entry->author->name) ? (string)$entry->author->name : 'Anonymous';
        $author_email = isset($entry->author->email) ? (string)$entry->author->email : '';
        
        // Find parent post ref
        $parent_ref = '';
        if (isset($entry->children('http://schemas.google.com/thr/2007')->{'in-reply-to'})) {
            $parent_ref = (string)$entry->children('http://schemas.google.com/thr/2007')->{'in-reply-to'}->attributes()->ref;
        }
        
        $comments[] = [
            'parent_ref' => $parent_ref,
            'author' => $author_name,
            'email' => $author_email,
            'content' => $content,
            'published' => $published
        ];
    }
}

$total_posts = count($posts);
report_progress(30, "Found {$total_posts} posts to import.");

// Detect Environment
$is_wp = file_exists(__DIR__ . '/wp-load.php');
$is_joomla = file_exists(__DIR__ . '/configuration.php') && file_exists(__DIR__ . '/includes/framework.php');

if ($is_wp) {
    // ----------------------------------------------------
    // WORDPRESS IMPORT
    // ----------------------------------------------------
    report_progress(35, "WordPress environment detected. Importing...");
    define('WP_USE_THEMES', false);
    require_once __DIR__ . '/wp-load.php';
    
    global $wpdb;
    
    $idx = 0;
    foreach ($posts as $orig_id => &$post) {
        $post_data = [
            'post_title'   => $post['title'],
            'post_content' => $post['content'],
            'post_status'  => 'publish',
            'post_date'    => date('Y-m-d H:i:s', strtotime($post['published'])),
            'post_type'    => 'post',
            'tags_input'   => $post['tags']
        ];
        
        $post_id = wp_insert_post($post_data);
        if ($post_id && !is_wp_error($post_id)) {
            $post['wp_post_id'] = $post_id;
        }
        
        $idx++;
        if ($idx % 10 === 0 && $total_posts > 0) {
            $progress = 35 + intval(($idx / $total_posts) * 45);
            report_progress($progress, "Imported {$idx}/{$total_posts} posts into WordPress...");
        }
    }
    
    report_progress(80, "Importing comments into WordPress...");
    foreach ($comments as $comment) {
        $orig_post_id = $comment['parent_ref'];
        if (isset($posts[$orig_post_id]) && $posts[$orig_post_id]['wp_post_id'] > 0) {
            $wp_post_id = $posts[$orig_post_id]['wp_post_id'];
            wp_insert_comment([
                'comment_post_ID'      => $wp_post_id,
                'comment_author'       => $comment['author'],
                'comment_author_email' => $comment['email'],
                'comment_content'      => $comment['content'],
                'comment_date'         => date('Y-m-d H:i:s', strtotime($comment['published'])),
                'comment_approved'     => 1,
            ]);
        }
    }
    
} elseif ($is_joomla) {
    // ----------------------------------------------------
    // JOOMLA IMPORT
    // ----------------------------------------------------
    report_progress(35, "Joomla environment detected. Importing...");
    define('_JEXEC', 1);
    define('JPATH_BASE', __DIR__);
    require_once __DIR__ . '/includes/defines.php';
    require_once __DIR__ . '/includes/framework.php';
    
    // Joomla DB connection
    $db = JFactory::getDbo();
    
    // Get table prefix
    $app = JFactory::getApplication('site');
    $config = JFactory::getConfig();
    $prefix = $config->get('dbprefix');
    
    // Create Blogger category in Joomla if not exists
    $cat_query = "SELECT id FROM {$prefix}categories WHERE extension = 'com_content' AND alias = 'blogger-import'";
    $db->setQuery($cat_query);
    $cat_id = $db->loadResult();
    
    if (!$cat_id) {
        // Simple insert into categories
        $insert_cat = "INSERT INTO {$prefix}categories (title, alias, extension, published, access, language, metadata) 
                       VALUES ('Blogger Import', 'blogger-import', 'com_content', 1, 1, '*', '{}')";
        $db->setQuery($insert_cat);
        $db->execute();
        $cat_id = $db->insertid();
    }
    
    $idx = 0;
    foreach ($posts as $orig_id => &$post) {
        $alias = JApplicationHelper::stringURLSafe($post['title']);
        $published_date = date('Y-m-d H:i:s', strtotime($post['published']));
        
        $insert_art = "INSERT INTO {$prefix}content (title, alias, introtext, state, catid, created, created_by, access, metadata) 
                       VALUES (" . $db->quote($post['title']) . ", " . $db->quote($alias) . ", " . $db->quote($post['content']) . ", 1, " . intval($cat_id) . ", " . $db->quote($published_date) . ", 99, 1, '{}')";
        $db->setQuery($insert_art);
        $db->execute();
        $art_id = $db->insertid();
        $post['jm_post_id'] = $art_id;
        
        $idx++;
        if ($idx % 10 === 0 && $total_posts > 0) {
            $progress = 35 + intval(($idx / $total_posts) * 55);
            report_progress($progress, "Imported {$idx}/{$total_posts} posts into Joomla...");
        }
    }
    
    // Comments: Joomla core doesn't have a built-in comment system by default,
    // comments are skipped or could be stored in custom table if Kunena or JComments is present.
    // For simplicity, we just skip Joomla comments or notify that they are skipped.
} else {
    report_progress(100, "Error: Unknown CMS environment. Neither WordPress nor Joomla detected in the root path.");
    exit(1);
}

report_progress(100, "Blogger backup imported successfully!");
?>
