REPORT_CONFIG = {
    # Core Business Parameters
    'primary_bank': 'Kookmin Bank',
    'comparison_banks': ['Hana', 'Woori', 'Shinhan Bank'],
    'credit_card_product_type': 'Premium Credit Cards',
    'language': 'Korean',
    'demo_mode': True,  # Toggle for demo mode (generate one section) vs full report
    'orientation': 'landscape',  # Report orientation - can be 'landscape' or 'portrait'
    
    'analysis_focus': [
        'Market Share and Growth',
        'Revenue and Profitability',
        'Customer Acquisition Cost',
        'Customer Lifetime Value',
        'Digital Transformation Impact',
        'Competitive Positioning'
    ],
    
    'performance_metrics': [
        'Card Issuance Volume',
        'Transaction Volume',
        'Revenue per Card',
        'Customer Retention Rate',
        'Digital Adoption Rate',
        'Market Share by Segment'
    ],
    
    'market_segments': [
        'High Net Worth Individuals',
        'Business Professionals',
        'Digital-First Customers',
        'Loyalty Program Members'
    ],
    
    'report_sections': [
        'Executive Summary',
        'Premium Credit Card Product Comparison',
        'Pricing and Fee Analysis',
        'Rewards and Benefits Comparison',
        'Digital Features and Mobile Banking',
        'Customer Service and Support',
        'Market Performance Metrics',
        'Recommendations and Next Steps'
    ],
    
    # Structure Mode
    'strict_structure': False,
    
    # Writing Style
    'writing_style': {
        'tone': 'Executive and Strategic',
        'formality_level': 'High',
        'emphasis': ['Data-Driven Insights', 'Strategic Implications', 'ROI Impact']
    },
    
    # Model Configuration
    'model_id': 'gemini-2.5-pro-preview-05-06',
    'flash_model_id': 'gemini-2.5-flash-preview-04-17',
    
    # Safety Settings
    'safety_settings': [
        {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'OFF'},
        {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'OFF'},
        {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'OFF'},
        {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'OFF'}
    ]
}