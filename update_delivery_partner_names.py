#!/usr/bin/env python3
"""
Script to update delivery partner names with more unique, varied names
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from app.models import User

# Define unique name templates per area - Each name is distinct and includes area
NAMES_BY_AREA = {
    'Bago': ['Aung Ko (Bago)', 'Thiha Soe (Bago)', 'Myo Win (Bago)'],
    'Dawei': ['Hla Min (Dawei)', 'Zaw Oo (Dawei)', 'Su Su (Dawei)'],
    'Kalay': ['Kyaw Thu (Kalay)', 'Nyein Chan (Kalay)', 'Aye Aye (Kalay)'],
    'Latha': ['Min Naing (Latha)', 'Htun Htun (Latha)', 'May Thet (Latha)'],
    'Magwe': ['Soe Moe (Magwe)', 'Khin Mar (Magwe)', 'Than Aung (Magwe)'],
    'Mandalay': ['Myint Aung (Mandalay)', 'San San (Mandalay)', 'Zaw Zaw (Mandalay)'],
    'Matel': ['Ko Ko (Matel)', 'Su Mon (Matel)', 'Aung Myint (Matel)'],
    'Mawlamyine': ['Naing Win (Mawlamyine)', 'Hnin Wai (Mawlamyine)', 'Myo Min (Mawlamyine)'],
    'Monywa': ['Hla Win (Monywa)', 'Yin Yin (Monywa)', 'Soe Win (Monywa)'],
    'Myeik': ['Than Tun (Myeik)', 'Khin Htay (Myeik)', 'Aung Zin (Myeik)'],
    'Myitkyinar': ['Kyaw Zin (Myitkyinar)', 'Nyein Nyein (Myitkyinar)', 'Min Ko (Myitkyinar)'],
    'Naypyitaw': ['Aung Htun (Naypyitaw)', 'Su Su Win (Naypyitaw)', 'Zaw Min (Naypyitaw)'],
    'North Okkalapa': ['Ko Htut (North Okkalapa)', 'Ei Ei (North Okkalapa)', 'Myo Hlaing (North Okkalapa)'],
    'Pathein': ['Win Aung (Pathein)', 'Khin Khin (Pathein)', 'Soe Naing (Pathein)'],
    'Pyay': ['Aung Myo (Pyay)', 'Hla Hla (Pyay)', 'Than Zaw (Pyay)'],
    'Sittwe': ['Kyaw Min (Sittwe)', 'Su Su Mon (Sittwe)', 'Aung Ko Ko (Sittwe)'],
    'South Dagon': ['Hla Myint (South Dagon)', 'Nyein Su (South Dagon)', 'Min Aung (South Dagon)'],
    'Taunggu': ['Soe Htut (Taunggu)', 'Khin Mar Win (Taunggu)', 'Zaw Than (Taunggu)'],
    'Taunggyi': ['Aung Naing (Taunggyi)', 'Su Wai (Taunggyi)', 'Myo Thant (Taunggyi)']
}

def update_delivery_partner_names():
    """Update all delivery partner names with more unique names"""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("="*60, flush=True)
    print("🔄 UPDATING DELIVERY PARTNER NAMES", flush=True)
    print("="*60, flush=True)
    
    app = create_app()
    with app.app_context():
        try:
            # Get all delivery partners grouped by area
            all_dps = User.query.filter_by(role='delivery_partner', is_active=True).order_by(
                User.area, User.id
            ).all()
            
            if not all_dps:
                print("⚠️  No delivery partners found!")
                return False
            
            print(f"\n📋 Found {len(all_dps)} delivery partners to update\n")
            
            # Group by area
            by_area = {}
            for dp in all_dps:
                area = dp.area or 'Unknown'
                if area not in by_area:
                    by_area[area] = []
                by_area[area].append(dp)
            
            updated_count = 0
            
            for area, partners in by_area.items():
                print(f"📍 Updating {len(partners)} delivery partners in {area}...")
                
                # Get names for this area
                if area in NAMES_BY_AREA:
                    names = NAMES_BY_AREA[area]
                else:
                    # Generate default names if area not in list
                    names = [f'Partner {i+1}' for i in range(len(partners))]
                
                # Update each partner with a unique name
                for i, partner in enumerate(partners):
                    if i < len(names):
                        new_name = names[i]  # Use the predefined name directly
                    else:
                        # If more than 3 partners, use numbered names
                        new_name = f"{area} Delivery Partner {i+1}"
                    
                    old_name = partner.name
                    partner.name = new_name
                    updated_count += 1
                    print(f"   ✅ {partner.unique_id}: '{old_name}' → '{new_name}'")
                    sys.stdout.flush()
            
            # Commit all changes
            db.session.commit()
            
            print(f"\n✅ Successfully updated {updated_count} delivery partner names!")
            print("="*60)
            
            # Display summary
            print("\n📋 UPDATED SUMMARY:")
            print("="*60)
            for area, partners in by_area.items():
                print(f"\n📍 {area}:")
                for partner in partners:
                    print(f"   • {partner.unique_id} - {partner.name} ({partner.email})")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error updating names: {str(e)}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    try:
        success = update_delivery_partner_names()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Update cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

