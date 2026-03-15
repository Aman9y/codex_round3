(function() {
    'use strict';
    
    let tabSwitchCount = 0;
    let isPageUnloading = false;
    
    // Tab switch detection
    window.addEventListener('beforeunload', function() {
        isPageUnloading = true;
    });
    
    document.addEventListener('visibilitychange', function() {
        if (document.hidden && !isPageUnloading) {
            tabSwitchCount++;
            
            fetch('/tab-switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ count: tabSwitchCount })
            }).catch(e => console.error('Failed to log tab switch:', e));
        }
    });
    
    // Block dangerous key combinations
    document.addEventListener('keydown', function(e) {
        let blocked = false;
        
        // Copy/Paste protection
        if (e.ctrlKey && ['c', 'v', 'x'].includes(e.key)) blocked = true;
        
        // Dev tools protection
        if (e.key === 'F12') blocked = true;
        if (e.ctrlKey && e.shiftKey && ['I', 'J', 'C'].includes(e.key)) blocked = true;
        if (e.ctrlKey && e.key === 'u') blocked = true;
        
        // Screenshot protection
        if (e.key === 'PrintScreen') blocked = true;
        
        if (blocked) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    });
    
    // Block right-click
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        return false;
    });
    
    // Disable text selection
    document.body.style.userSelect = 'none';
    document.body.style.webkitUserSelect = 'none';
    
})();