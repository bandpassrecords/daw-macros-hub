# Cubase Macros Shop

A Django web application for sharing and managing Cubase Key Commands and macros. Users can upload their Key Commands XML files, share individual macros with the community, and discover popular macros from other users.

## Features

### 🔑 **Key Commands Management**
- Upload Cubase Key Commands XML files
- Parse and extract individual macros from uploaded files
- Download original files or create custom macro collections
- Cubase version compatibility tracking

### 👥 **Community Sharing**
- Make macros public for community discovery
- Browse popular and trending macros
- Rate and favorite macros
- Search and filter by category, Cubase version, and more

### 📊 **Analytics & Discovery**
- View macro popularity statistics
- Track downloads and usage
- Browse by categories (Transport, Edit, Tools, etc.)
- User profiles with upload history

### 🎯 **User Features**
- User registration and authentication
- Personal dashboard with statistics
- Profile management with preferences
- Private/public macro visibility control

## Installation

### Prerequisites
- Python 3.8+
- Django 4.2+
- See `requirements.txt` for complete dependencies

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd cubasemacros
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure settings**
   ```bash
   # Copy and edit settings if needed
   cp cubase_macros_shop/settings.py cubase_macros_shop/local_settings.py
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Populate initial data**
   ```bash
   python manage.py populate_data
   ```

7. **Create superuser** (optional)
   ```bash
   python manage.py createsuperuser
   ```

8. **Run development server**
   ```bash
   python manage.py runserver
   ```

9. **Access the application**
   - Main site: http://localhost:8000/
   - Admin interface: http://localhost:8000/admin/

## Usage

### For Users

#### **Uploading Key Commands**
1. Export your Key Commands from Cubase:
   - Open Cubase → Studio → Studio Setup
   - Click "Key Commands" in the left panel
   - Click "Export" and save your XML file

2. Upload to the platform:
   - Register/login to your account
   - Navigate to "Upload" section
   - Select your XML file and add details
   - Choose visibility (public/private)

**Note**: The application now focuses on the "Macros" section of your Key Commands XML file. Each macro entry includes Name, Category, Description, and Key Binding information.

#### **Discovering Macros**
- **Browse All**: View all public macros with filtering options
- **Categories**: Browse by macro categories (Transport, Edit, etc.)
- **Popular**: See trending and highest-rated macros
- **Search**: Find specific macros by name or functionality

#### **Creating Custom Downloads**
1. View any uploaded Key Commands file
2. Click "Select & Download" 
3. Choose specific macros you want
4. Download custom XML file with only selected macros

### For Developers

#### **Project Structure**
```
cubasemacros/
├── cubase_macros_shop/      # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                       # Core app (homepage, static pages)
├── accounts/                   # User management
├── macros/                     # Main macros functionality
│   ├── models.py              # Database models
│   ├── views.py               # View logic
│   ├── forms.py               # Django forms
│   ├── utils.py               # XML parsing utilities
│   └── admin.py               # Admin interface
├── templates/                  # HTML templates
├── static/                     # CSS, JS, images
├── media/                      # User uploads
└── requirements.txt
```

#### **Key Models**
- **KeyCommandsFile**: Uploaded XML files
- **Macro**: Individual macros from files
- **MacroCategory**: Macro categories
- **MacroVote**: User ratings
- **MacroFavorite**: User favorites
- **UserProfile**: Extended user data

#### **XML Parsing**
The `KeyCommandsParser` class in `macros/utils.py` handles:
- XML validation and parsing of Macros structure
- Direct macro extraction from `<list name="Macros">` section
- Category, name, description, and key binding processing
- Error handling and validation

**Expected XML Structure:**
```xml
<KeyCommands>
    <list name="Macros" type="list">
        <item>
            <string name="Name" value="Macro Name"/>
            <list name="Commands" type="list">
                <item>
                    <string name="Category" value="Category Name"/>
                    <string name="Name" value="Command Name"/>
                </item>
                <item>
                    <string name="Category" value="Another Category"/>
                    <string name="Name" value="Another Command"/>
                </item>
                <!-- More commands that make up this macro... -->
            </list>
        </item>
        <!-- More macro items... -->
    </list>
</KeyCommands>
```

## API Endpoints

### **Main URLs**
- `/` - Homepage
- `/accounts/` - User authentication
- `/macros/` - Macro browsing and management
- `/admin/` - Django admin interface

### **Key Pages**
- `/macros/` - Browse all macros
- `/macros/categories/` - Category listing
- `/macros/popular/` - Popular macros
- `/macros/upload/` - Upload Key Commands
- `/macros/my-files/` - User's uploaded files

## Testing

### **Sample Data**
The project includes:
- Sample Key Commands XML file (`sample_key_commands.xml`) in the new Macros format
- Management command for initial data (`populate_data`)
- Test users with sample data
- 20 sample macros across categories like Audio, Transport, Track, MIDI, etc.

### **Test Users**
Created by `populate_data` command:
- Username: `demo_user`, Password: `testpass123`
- Username: `macro_creator`, Password: `testpass123`
- Username: `cubase_pro`, Password: `testpass123`

### **Manual Testing**
1. Register a new account
2. Upload the sample XML file
3. Browse and interact with macros
4. Test download functionality

## Configuration

### **Environment Variables**
Create a `.env` file for sensitive settings:
```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

### **Production Settings**
For production deployment:
- Set `DEBUG=False`
- Configure proper database (PostgreSQL recommended)
- Set up static file serving
- Configure email backend for notifications
- Set proper `ALLOWED_HOSTS`

## Contributing

### **Development Setup**
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

### **Code Style**
- Follow Django best practices
- Use Django's built-in features where possible
- Add comments for complex logic
- Include docstrings for functions

## Troubleshooting

### **Common Issues**

**Template Syntax Errors**
- Check Django template syntax
- Ensure proper variable passing from views

**Upload Issues**
- Verify file format (XML only)
- Check file size limits in settings
- Ensure proper XML structure

**Database Issues**
- Run migrations: `python manage.py migrate`
- Reset if needed: Delete `db.sqlite3` and re-migrate

**Static Files**
- Run: `python manage.py collectstatic`
- Check `STATIC_URL` and `STATIC_ROOT` settings

### **Logs**
Check Django logs for detailed error information:
```bash
python manage.py runserver --verbosity=2
```

## License

This project is open source. Feel free to modify and distribute.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Django documentation
3. Create an issue in the repository

## Acknowledgments

- Built with Django framework
- Uses Bootstrap 5 for UI
- Font Awesome for icons
- Cubase community for inspiration 