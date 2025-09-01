# 🔄 QTable Backend: Two-Sided Platform Adaptation Plan

## 📊 Current State Analysis

### ✅ **Already Production-Ready:**
- Multi-tenant restaurant management system
- Real-time WebSocket updates per restaurant
- JWT authentication with role-based access
- Optimized database queries with caching
- Railway deployment configuration
- Enterprise-grade table management

### 🎯 **Required Extensions for Two-Sided Platform:**

---

## 🏗️ **Phase 1: Customer-Facing API Extensions**

### **New Models Needed:**

#### 1. **Customer Model** (separate from restaurant users)
```python
class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 2. **Restaurant Public Profile** (extend existing)
```python
# Add to existing Restaurant model:
    is_public = Column(Boolean, default=True)
    description = Column(Text)
    cuisine_type = Column(String)
    price_range = Column(String)  # $, $$, $$$, $$$$
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(String)
    website = Column(String)
    hours_monday = Column(String)  # "09:00-22:00"
    hours_tuesday = Column(String)
    # ... other days
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
```

#### 3. **Availability Slots Model**
```python
class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    restaurant_id = Column(String, ForeignKey("restaurants.id"))
    date = Column(Date)
    time_slot = Column(Time)  # 18:00, 18:30, 19:00, etc.
    party_size = Column(Integer)
    available_tables = Column(Integer)
    is_available = Column(Boolean, default=True)
```

#### 4. **Customer Reservations Model**
```python
class CustomerReservation(Base):
    __tablename__ = "customer_reservations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    restaurant_id = Column(String, ForeignKey("restaurants.id"))
    customer_id = Column(String, ForeignKey("customers.id"))
    date = Column(Date)
    time = Column(Time)
    party_size = Column(Integer)
    status = Column(String, default="confirmed")  # confirmed, cancelled, seated, completed
    special_requests = Column(Text)
    table_id = Column(String, ForeignKey("restaurant_tables.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 🛠️ **Phase 2: New API Endpoints**

### **Public Restaurant Discovery:**
```python
# No authentication required
GET /public/restaurants?lat={lat}&lon={lon}&radius={km}
GET /public/restaurants/{restaurant_id}
GET /public/restaurants/{restaurant_id}/availability?date={date}&party_size={size}
```

### **Customer Authentication:**
```python
POST /customer/register
POST /customer/login
POST /customer/verify-email
```

### **Customer Reservations:**
```python
POST /customer/reservations
GET /customer/reservations
PUT /customer/reservations/{reservation_id}
DELETE /customer/reservations/{reservation_id}
```

### **Restaurant Availability Management:**
```python
# For restaurant staff
POST /restaurants/{restaurant_id}/availability
PUT /restaurants/{restaurant_id}/availability/{slot_id}
GET /restaurants/{restaurant_id}/customer-reservations
```

---

## 🔄 **Phase 3: WebSocket Extensions**

### **Customer-Side WebSocket Events:**
```python
# Customer app subscriptions
"reservation_confirmed"
"reservation_updated" 
"table_ready"
"estimated_wait_time"
```

### **Restaurant-Side Extensions:**
```python
# Additional events for restaurant app
"customer_reservation_received"
"customer_checked_in"
"availability_updated"
```

---

## 🗺️ **Phase 4: Geo-Location Features**

### **PostgreSQL Extensions:**
```sql
-- Enable PostGIS for advanced geo queries
CREATE EXTENSION IF NOT EXISTS postgis;

-- Add spatial index
CREATE INDEX idx_restaurants_location ON restaurants USING GIST (ST_Point(longitude, latitude));
```

### **Geo Search Implementation:**
```python
def find_nearby_restaurants(lat: float, lon: float, radius_km: float = 10):
    # PostgreSQL with PostGIS
    query = """
    SELECT *, ST_Distance(
        ST_Point(longitude, latitude)::geography,
        ST_Point(%s, %s)::geography
    ) / 1000 AS distance_km
    FROM restaurants 
    WHERE is_public = true
    AND ST_DWithin(
        ST_Point(longitude, latitude)::geography,
        ST_Point(%s, %s)::geography,
        %s * 1000
    )
    ORDER BY distance_km;
    """
```

---

## 📱 **Integration with Current QTable System**

### **Unified Flow:**
1. **Customer books** via customer app → Creates `CustomerReservation`
2. **WebSocket notification** → Restaurant staff sees new reservation
3. **Restaurant staff** can convert reservation to table assignment
4. **Real-time updates** → Customer sees table assignment/wait time
5. **Existing table management** → Use current QTable system for seating

### **Data Relationship:**
```
CustomerReservation → (when seated) → Guest → Table
```

---

## 🚀 **Implementation Priority**

### **Week 1: Database Extensions**
- [ ] Add Customer model
- [ ] Extend Restaurant model with public fields
- [ ] Create AvailabilitySlot model
- [ ] Create CustomerReservation model
- [ ] Database migrations

### **Week 2: Customer API**
- [ ] Customer registration/login
- [ ] Public restaurant discovery
- [ ] Availability viewing
- [ ] Reservation booking

### **Week 3: Restaurant Integration**
- [ ] Customer reservation management for restaurants
- [ ] Availability slot management
- [ ] Integration with existing table system

### **Week 4: Real-time & Geo**
- [ ] Extended WebSocket events
- [ ] Geo-location search
- [ ] Performance optimization

---

## 💡 **Architecture Benefits**

### **Leveraging Existing QTable Backend:**
- ✅ **Table management system** already optimized
- ✅ **Real-time WebSocket** infrastructure ready
- ✅ **Multi-tenant architecture** supports multiple restaurants
- ✅ **Authentication system** can be extended for customers
- ✅ **Deployment pipeline** already configured

### **Seamless Integration:**
- Restaurant staff continues using existing QTable interface
- Customer reservations flow into existing table management
- Real-time updates work for both sides
- Single backend serves both customer and restaurant apps

---

## 🎯 **Next Steps**

1. **Review current QTable backend** capabilities
2. **Design database schema extensions** 
3. **Create customer-facing API endpoints**
4. **Extend WebSocket event system**
5. **Implement geo-location features**
6. **Test two-sided integration**

**Your QTable backend is the perfect foundation for this two-sided platform! 🚀**
