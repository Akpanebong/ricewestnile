/**
 * Accounting Format Utilities
 * Provides functions for formatting numbers in accounting format (with commas)
 */

/**
 * Format a number with comma separators and 2 decimal places
 * @param {number} value - The value to format
 * @param {string} locale - The locale to use (default: browser locale)
 * @returns {string} Formatted number with commas
 */
function formatAccountingAmount(value, locale = undefined) {
    if (value === null || value === undefined || value === '') {
        return '0.00';
    }
    
    const num = parseFloat(value);
    if (isNaN(num)) {
        return '0.00';
    }
    
    return num.toLocaleString(locale, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

/**
 * Format a currency amount with symbol and comma separators
 * @param {number} value - The value to format
 * @param {string} currency - Currency code (e.g., 'UGX', 'USD')
 * @param {string} locale - The locale to use (default: browser locale)
 * @returns {string} Formatted currency (e.g., "UGX 1,234.56")
 */
function formatCurrency(value, currency = 'UGX', locale = undefined) {
    if (value === null || value === undefined || value === '') {
        return `${currency} 0.00`;
    }
    
    const num = parseFloat(value);
    if (isNaN(num)) {
        return `${currency} 0.00`;
    }
    
    const formatted = num.toLocaleString(locale, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    
    return `${currency} ${formatted}`;
}

/**
 * Parse a formatted accounting amount back to a number
 * @param {string} formatted - The formatted string (e.g., "1,234.56")
 * @returns {number} The numeric value
 */
function parseAccountingAmount(formatted) {
    if (!formatted) return 0;
    // Remove all commas and parse
    return parseFloat(String(formatted).replace(/,/g, ''));
}

/**
 * Format all elements with data-accounting-format attribute
 * Usage: <span data-accounting-format="1234.56">0.00</span>
 */
function formatPageAmounts() {
    document.querySelectorAll('[data-accounting-format]').forEach(el => {
        const value = el.getAttribute('data-accounting-format');
        const currency = el.getAttribute('data-currency') || '';
        
        if (currency) {
            el.textContent = formatCurrency(value, currency);
        } else {
            el.textContent = formatAccountingAmount(value);
        }
    });
}

/**
 * Apply accounting format to input fields on load
 * Usage: <input class="currency-input" value="1234.56">
 */
function formatInputFields() {
    document.querySelectorAll('input.currency-input').forEach(input => {
        if (input.value) {
            input.value = formatAccountingAmount(input.value);
        }
    });
}

/**
 * Initialize event listeners for currency inputs
 */
function initCurrencyInputs() {
    document.querySelectorAll('input.currency-input').forEach(input => {
        // Format on blur
        input.addEventListener('blur', function() {
            if (this.value) {
                const numValue = parseAccountingAmount(this.value);
                this.value = formatAccountingAmount(numValue);
            }
        });
        
        // Remove formatting on focus for editing
        input.addEventListener('focus', function() {
            if (this.value) {
                this.value = parseAccountingAmount(this.value);
            }
        });
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    formatPageAmounts();
    formatInputFields();
    initCurrencyInputs();
});
