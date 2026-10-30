/**
 * dom_walker.js - Script untuk ekstraksi struktur DOM + atribut ARIA + bounding box
 * 
 * Diinjeksikan ke browser via execute_script Playwright.
 * Return: Array of element objects dengan metadata lengkap untuk scoring.
 */

(function extractDOMTree() {
  const results = [];
  let elementCounter = 0;

  /**
   * Cek apakah elemen visible dan interaktable
   */
  function isElementVisible(element) {
    if (!element || !element.getBoundingClientRect) return false;
    
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    
    // Cek dimensi
    if (rect.width === 0 || rect.height === 0) return false;
    
    // Cek visibility
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    
    // Cek apakah di viewport (atau setidaknya partially visible)
    if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
    if (rect.right < 0 || rect.left > window.innerWidth) return false;
    
    return true;
  }

  /**
   * Ekstrak bounding box dalam format yang konsisten
   */
  function getBoundingBox(element) {
    const rect = element.getBoundingClientRect();
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      top: Math.round(rect.top),
      left: Math.round(rect.left),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom)
    };
  }

  /**
   * Ekstrak semua atribut ARIA yang relevan
   */
  function getARIAAttributes(element) {
    const aria = {};
    const attributes = element.attributes;
    
    for (let i = 0; i < attributes.length; i++) {
      const attr = attributes[i];
      if (attr.name.startsWith('aria-') || attr.name === 'role') {
        aria[attr.name] = attr.value;
      }
    }
    
    return aria;
  }

  /**
   * Deteksi role implisit dari tag name
   */
  function getImplicitRole(element) {
    const tagName = element.tagName.toLowerCase();
    const roleMap = {
      'button': 'button',
      'a': 'link',
      'input': element.type === 'submit' || element.type === 'button' ? 'button' : 'textbox',
      'textarea': 'textbox',
      'select': 'combobox',
      'img': 'img',
      'nav': 'navigation',
      'main': 'main',
      'header': 'banner',
      'footer': 'contentinfo',
      'article': 'article',
      'section': 'region',
      'form': 'form',
      'h1': 'heading',
      'h2': 'heading',
      'h3': 'heading',
      'h4': 'heading',
      'h5': 'heading',
      'h6': 'heading'
    };
    
    return roleMap[tagName] || null;
  }

  /**
   * Ekstrak text content yang visible
   */
  function getVisibleText(element) {
    const clone = element.cloneNode(true);
    const scriptsAndStyles = clone.querySelectorAll('script, style');
    scriptsAndStyles.forEach(el => el.remove());
    
    let text = clone.textContent || '';
    text = text.replace(/\s+/g, ' ').trim();
    return text;
  }

  /**
   * Cek apakah elemen interaktif
   */
  function isInteractive(element) {
    const tagName = element.tagName.toLowerCase();
    const interactiveTags = ['button', 'a', 'input', 'select', 'textarea'];
    
    if (interactiveTags.includes(tagName)) return true;
    if (element.hasAttribute('onclick')) return true;
    if (element.getAttribute('role') === 'button') return true;
    if (element.getAttribute('role') === 'link') return true;
    if (element.hasAttribute('tabindex') && element.tabIndex >= 0) return true;
    
    const computedStyle = window.getComputedStyle(element);
    if (computedStyle.cursor === 'pointer') return true;
    
    return false;
  }

  /**
   * Generate CSS selector path sederhana
   */
  function getSimpleSelector(element) {
    if (element.id) {
      return `#${element.id}`;
    }
    
    const path = [];
    let current = element;
    
    while (current && current.nodeType === Node.ELEMENT_NODE && current.tagName !== 'HTML') {
      let selector = current.tagName.toLowerCase();
      
      if (current.className) {
        const classes = Array.from(current.classList)
          .filter(c => c && !c.includes(' '))
          .slice(0, 2)
          .join('.');
        if (classes) selector += '.' + classes;
      }
      
      path.unshift(selector);
      current = current.parentElement;
      
      if (path.length >= 4) break;
    }
    
    return path.join(' > ');
  }

  /**
   * Walker utama - traverse DOM tree
   */
  function walkDOM(element, depth = 0) {
    if (depth > 15) return;
    if (!isElementVisible(element)) return;
    
    const tagName = element.tagName.toLowerCase();
    const aria = getARIAAttributes(element);
    const implicitRole = getImplicitRole(element);
    const explicitRole = element.getAttribute('role');
    const role = explicitRole || implicitRole;
    
    const isRelevant = 
      isInteractive(element) || 
      role !== null || 
      Object.keys(aria).length > 0 ||
      ['nav', 'header', 'footer', 'main', 'section', 'article', 'form'].includes(tagName);
    
    if (isRelevant) {
      const text = getVisibleText(element);
      const bbox = getBoundingBox(element);
      
      results.push({
        id: `elem_${elementCounter++}`,
        tagName: tagName,
        role: role,
        aria: aria,
        text: text.substring(0, 200),
        bbox: bbox,
        interactive: isInteractive(element),
        selector: getSimpleSelector(element),
        attributes: {
          id: element.id || null,
          name: element.getAttribute('name') || null,
          type: element.getAttribute('type') || null,
          href: element.getAttribute('href') || null,
          placeholder: element.getAttribute('placeholder') || null,
          value: element.value || null,
          disabled: element.disabled || false,
          readonly: element.readOnly || false
        }
      });
    }
    
    const children = element.children;
    for (let i = 0; i < children.length; i++) {
      walkDOM(children[i], depth + 1);
    }
  }

  try {
    walkDOM(document.body, 0);
  } catch (error) {
    console.error('Error saat extract DOM:', error);
    return { error: error.message, results: [] };
  }

  return {
    timestamp: new Date().toISOString(),
    url: window.location.href,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight
    },
    totalElements: results.length,
    elements: results
  };
})();

