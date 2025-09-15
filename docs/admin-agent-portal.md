# Admin + Agent Portal — Complete API Documentation

Goal: Build a role-aware (admin/agent) dashboard to manage users, agents, properties, visits, and bookings for the real-estate + short-stays platform.

Stack: React + Redux Toolkit (with RTK Query) + Shadcn UI. Backend: FastAPI + Supabase Auth.

## Roles & RBAC

- Roles: `user`, `agent`, `admin` (stored on `users.role`).
- Server enforces RBAC; client should also gate navigation/actions by role.
- Agents are linked via `users.agent_id` (the agent's own user row should also have `agent_id` set to their `agents.id`).

## Frontend Architecture

- Routing
  - Admin: `/dashboard`, `/users`, `/users/:id`, `/agents`, `/agents/:id`, `/properties`, `/properties/:id`, `/visits`, `/bookings`, `/analytics`.
  - Agent: `/dashboard`, `/agents/me`, `/clients`, `/clients/:id`, `/properties`, `/visits`, `/bookings`, `/profile`.
- State
  - Slices: `auth`, `ui`, `notifications`.
  - RTK Query APIs: `authApi`, `usersApi`, `agentsApi`, `propertiesApi`, `visitsApi`, `bookingsApi`, `amenitiesApi`, `uploadApi`, `coreApi`.
  - Base URL: `/api/v1`. Inject `Authorization: Bearer <token>` in `prepareHeaders`.
- UI Kit
  - Shadcn data tables (with server-side pagination), forms (react-hook-form + zod), sheets/dialogs for edits, toasts for actions.

## Key Features

### Admin

- Users: list/search/paginate, view details, edit, assign agent.
- Agents: list/create/edit/deactivate, toggle availability, workload/stats.
- Properties: create for any owner, edit, delete.
- Visits: global listing with filters, mark completed.
- Bookings: global listing with filters, process payments, add reviews.
- Amenities: fetch list for forms.
- Uploads: generic file upload (returns public URL).
- Core Features: Bug reports, pages management, app updates.

### Agent

- My profile: `/agents/me` (from linked `agent_id`).
- Clients: list assigned users; edit limited fields (contact, preferences).
- Properties: manage only for users they manage.
- Visits: list for managed users/properties; mark completed with notes/feedback.
- Bookings: list for managed users/properties; payments/reviews when authorized.
- Uploads: generic upload for assets.


## API Endpoints (Portal Scope)

Base path: `/api/v1`

### Users (Admin/Agent)

#### GET `/users/`
- **Description**: List users with pagination and search
- **Access**:
  - Admin: Can view all users, optionally filter by agent
  - Agent: Can only view assigned users
- **Query Parameters**:
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
  - `q`: str (optional) - Search by name, email, or phone
  - `agent_id`: int (optional, admin only) - Filter users by assigned agent
- **Response**: `PaginatedResponse`

#### GET `/users/{user_id}/`
- **Description**: Get user details by ID
- **Access**:
  - Admin: Can access any user
  - Agent: Can only access assigned users
- **Response**: Complete user object with preferences and agent details

#### PUT `/users/{user_id}/`
- **Description**: Update user details
- **Access**:
  - Admin: Can update any field
  - Agent: Can update limited fields for assigned users (contact info, preferences)
- **Request Body**:
  ```json
  {
    "email": "new@example.com",
    "full_name": "John Doe",
    "phone": "+1234567890",
    "date_of_birth": "1990-01-01",
    "profile_image_url": "https://example.com/avatar.jpg",
    "preferences": {
      "property_type": ["apartment", "house"],
      "purpose": "rent",
      "budget_min": 10000,
      "budget_max": 50000,
      "bedrooms_min": 2,
      "bedrooms_max": 3,
      "area_min": 800,
      "area_max": 1500,
      "location_preference": ["Mumbai", "Delhi"],
      "max_distance_km": 10
    },
    "current_latitude": 19.0760,
    "current_longitude": 72.8777,
    "preferred_locations": ["Mumbai", "Delhi"],
    "notification_settings": {},
    "privacy_settings": {}
  }
  ```
- **Response**: Updated user object

#### POST `/users/{user_id}/assign-agent/`
- **Description**: Assign agent to specific user
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "agent_id": 1
  }
  ```
- **Response**: `{"message": "Agent assigned successfully"}`

### Users - Profile Management (All Users)

#### GET `/users/profile/`
- **Description**: Get current user's profile
- **Access**: Any authenticated user
- **Response**: Complete user profile with preferences

#### PUT `/users/profile/`
- **Description**: Update current user's profile
- **Access**: Any authenticated user
- **Request Body**: Same as `UserUpdate` schema
- **Response**: Updated user profile

#### PUT `/users/preferences/`
- **Description**: Update user preferences
- **Access**: Any authenticated user
- **Request Body**:
  ```json
  {
    "property_type": ["apartment", "house"],
    "purpose": "rent",
    "budget_min": 10000,
    "budget_max": 50000,
    "bedrooms_min": 2,
    "bedrooms_max": 3,
    "area_min": 800,
    "area_max": 1500,
    "location_preference": ["Mumbai", "Delhi"],
    "max_distance_km": 10
  }
  ```
- **Response**: `{"message": "Preferences updated successfully"}`

#### PUT `/users/location/`
- **Description**: Update user's current location
- **Access**: Any authenticated user
- **Request Body**:
  ```json
  {
    "latitude": 19.0760,
    "longitude": 72.8777
  }
  ```
- **Response**: `{"message": "Location updated successfully"}`

### Agents

#### GET `/agents/`
- **Description**: List all agents with pagination
- **Access**: Admin only
- **Query Parameters**:
  - `include_inactive`: bool (default: false) - Include deactivated agents
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
- **Response**: `PaginatedResponse`

#### POST `/agents/`
- **Description**: Create new agent
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "user_id": 123,
    "employee_id": "EMP001",
    "specialization": "luxury",
    "agent_type": "senior",
    "experience_level": "expert",
    "years_of_experience": 10,
    "bio": "Experienced luxury property specialist",
    "languages": ["English", "Hindi"],
    "working_hours": {},
    "commission_rate": 2.5,
    "service_areas": ["Mumbai", "Delhi"],
    "max_clients": 50,
    "is_available": true,
    "performance_metrics": {}
  }
  ```
- **Response**: Created agent object

#### PUT `/agents/{agent_id}`
- **Description**: Update agent details
- **Access**: Admin only
- **Request Body**: Agent update fields
- **Response**: Updated agent object

#### DELETE `/agents/{agent_id}`
- **Description**: Deactivate agent (soft delete)
- **Access**: Admin only
- **Response**: `{"message": "Agent deactivated successfully"}`

#### PATCH `/agents/{agent_id}/availability/`
- **Description**: Toggle agent availability
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "is_available": true
  }
  ```
- **Response**: Status message

#### GET `/agents/me/`
- **Description**: Get current agent's profile
- **Access**: Agent only
- **Response**: Complete agent profile with stats

#### GET `/agents/system/workload/`
- **Description**: Get system workload distribution
- **Access**: Admin only
- **Response**:
  ```json
  [
    {
      "agent_id": 1,
      "agent_name": "John Doe",
      "active_clients": 25,
      "pending_visits": 5,
      "active_bookings": 10,
      "utilization_rate": 0.75,
      "max_capacity": 50
    }
  ]
  ```

#### GET `/agents/system/stats/`
- **Description**: Get agent system statistics
- **Access**: Admin only
- **Response**:
  ```json
  {
    "total_agents": 10,
    "active_agents": 8,
    "average_clients_per_agent": 20.5,
    "total_clients_assigned": 205,
    "workload_distribution": {...},
    "performance_metrics": {...}
  }
  ```

### Agents - Public/User Endpoints

#### GET `/agents/assigned/`
- **Description**: Get current user's assigned agent
- **Access**: Any authenticated user
- **Response**: Agent object or null

#### POST `/agents/assign/`
- **Description**: Assign agent to current user (auto-assign if no agent_id)
- **Access**: Any authenticated user
- **Query Parameters**:
  - `agent_id`: int (optional) - Specific agent to assign
- **Response**: Assignment confirmation

#### GET `/agents/available/`
- **Description**: Get list of available agents with pagination
- **Access**: Any authenticated user
- **Query Parameters**:
  - `specialization`: str (optional) - Filter by specialization
  - `agent_type`: str (optional) - Filter by agent type
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
- **Response**: `PaginatedResponse`

#### GET `/agents/{agent_id}`
- **Description**: Get agent details
- **Access**: Any authenticated user
- **Response**: Agent profile (public fields only)

#### GET `/agents/{agent_id}/stats/`
- **Description**: Get agent details with performance statistics
- **Access**: Any authenticated user
- **Response**: Agent object with performance metrics

#### GET `/agents/{agent_id}/visits/`
- **Description**: Get visits handled by agent
- **Access**: Any authenticated user
- **Query Parameters**:
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
- **Response**: `PaginatedResponse`

#### GET `/agents/types/{agent_type}`
- **Description**: Get agents by type
- **Access**: Any authenticated user
- **Query Parameters**:
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
- **Response**: `PaginatedResponse`

#### GET `/agents/specializations/{specialization}`
- **Description**: Get agents by specialization
- **Access**: Any authenticated user
- **Query Parameters**:
  - `page`: int (default: 1, min: 1) - Page number
  - `limit`: int (default: 20, min: 1, max: 100) - Items per page
- **Response**: `PaginatedResponse`

### Properties

#### GET `/properties/`
- **Description**: Get properties with comprehensive filtering
- **Access**: Public (enhanced with authentication context)
- **Query Parameters**:
  - **Location**:
    - `lat`: float - Center latitude
    - `lng`: float - Center longitude
    - `radius`: float (default: 5) - Search radius in km
  - **Search**:
    - `q`: str - Text search in title/description
  - **Property**:
    - `property_type[]`: array - Filter by property type (house, apartment, builder_floor, room)
    - `purpose`: str - Filter by purpose (buy, rent, short_stay)
  - **Price**:
    - `price_min`: float - Minimum price
    - `price_max`: float - Maximum price
  - **Rooms**:
    - `bedrooms_min`: int - Minimum bedrooms
    - `bedrooms_max`: int - Maximum bedrooms
    - `bathrooms_min`: int - Minimum bathrooms
    - `bathrooms_max`: int - Maximum bathrooms
  - **Area**:
    - `area_min`: float - Minimum area in sqft
    - `area_max`: float - Maximum area in sqft
  - **Location**:
    - `city`: str - Filter by city
    - `locality`: str - Filter by locality
    - `pincode`: str - Filter by pincode
  - **Amenities**:
    - `amenities[]`: array - Filter by amenity IDs
    - `features[]`: array - Filter by features
  - **Additional**:
    - `parking_spaces_min`: int - Minimum parking spaces
    - `floor_number_min`: int - Minimum floor number
    - `floor_number_max`: int - Maximum floor number
    - `age_max`: int - Maximum property age in years
  - **Short Stay**:
    - `check_in`: date - Check-in date (YYYY-MM-DD)
    - `check_out`: date - Check-out date (YYYY-MM-DD)
    - `guests`: int - Number of guests
  - **Sorting**:
    - `sort_by`: str - Sort by (distance, price_low, price_high, newest, popular, relevance)
  - **Pagination**:
    - `page`: int (default: 1)
    - `limit`: int (default: 20, max: 100)
  - **Auth-aware**:
    - `exclude_swiped`: bool - Exclude properties user has already swiped
- **Response**:
  ```json
  {
    "properties": [
      {
        "id": 1,
        "title": "Modern 3BHK Apartment",
        "description": "Spacious apartment with modern amenities",
        "property_type": "apartment",
        "purpose": "rent",
        "base_price": 25000,
        "location": {
          "latitude": 19.0760,
          "longitude": 72.8777
        },
        "city": "Mumbai",
        "locality": "Andheri",
        "pincode": "400053",
        "area_sqft": 1200,
        "bedrooms": 3,
        "bathrooms": 2,
        "balconies": 2,
        "parking_spaces": 1,
        "floor_number": 5,
        "total_floors": 10,
        "age_of_property": 5,
        "max_occupancy": 6,
        "minimum_stay_days": 30,
        "amenities": [...],
        "features": ["gym", "pool", "security"],
        "images": [...],
        "main_image_url": "https://example.com/image.jpg",
        "owner_id": 123,
        "owner_name": "Property Owner",
        "owner_contact": "+1234567890",
        "status": "available",
        "liked": false,
        "user_has_scheduled_visit": false,
        "user_scheduled_visit_count": 0,
        "user_next_visit_date": null,
        "distance": 2.5,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "limit": 20,
    "total_pages": 5,
    "filters_applied": {...},
    "search_center": {"latitude": 19.0760, "longitude": 72.8777}
  }
  ```

#### GET `/properties/{property_id}`
- **Description**: Get property details
- **Access**: Public (enriched with user context if authenticated)
- **Response**: Property object with user-specific fields (liked, visit info)

#### POST `/properties/`
- **Description**: Create a new property
- **Access**:
  - Admin: Can create for any owner via `owner_id` query param
  - Agent: Can create for managed users via `owner_id` query param
  - User: Can create for self (no owner_id needed)
- **Query Parameters**:
  - `owner_id`: int (optional, admin/agent only) - Owner user ID
- **Request Body**:
  ```json
  {
    "title": "Modern 3BHK Apartment",
    "description": "Spacious apartment with modern amenities",
    "property_type": "apartment",
    "purpose": "rent",
    "base_price": 25000,
    "latitude": 19.0760,
    "longitude": 72.8777,
    "city": "Mumbai",
    "locality": "Andheri",
    "pincode": "400053",
    "area_sqft": 1200,
    "bedrooms": 3,
    "bathrooms": 2,
    "balconies": 2,
    "parking_spaces": 1,
    "floor_number": 5,
    "total_floors": 10,
    "age_of_property": 5,
    "max_occupancy": 6,
    "minimum_stay_days": 30,
    "amenity_ids": [1, 2, 3],
    "features": ["gym", "pool", "security"],
    "main_image_url": "https://example.com/image.jpg",
    "owner_name": "Property Owner",
    "owner_contact": "+1234567890"
  }
  ```
- **Response**: Created property object

#### PUT `/properties/{property_id}`
- **Description**: Update property details
- **Access**:
  - Admin: Can update any property
  - Agent: Can update if owner is a managed user
  - User: Can update own property
- **Request Body**: Property update fields
- **Response**: Updated property object

#### DELETE `/properties/{property_id}/`
- **Description**: Delete a property
- **Access**:
  - Admin: Can delete any property
  - Agent: Can delete if owner is a managed user
  - User: Can delete own property
- **Response**: `{"message": "Property deleted successfully"}`

### Properties - Additional Endpoints

#### GET `/properties/recommendations/`
- **Description**: Get property recommendations
- **Access**: Public (personalized with authentication)
- **Query Parameters**:
  - `limit`: int (default: 10, min: 1, max: 50)
- **Response**: Array of recommended properties

## Property Creation (Admin/Agent Portal)

This section provides a complete, copy-pasteable guide to build the Admin/Agent portal “Create Property” page: data dependencies, RBAC, form structure, map/location capture, image handling via Supabase, request/response contracts, and example RTK Query hooks.

### Roles & Authorization

- Admin: Creates property for any user by passing `owner_id` as a query param.
- Agent: Creates property only for users they manage by passing `owner_id` the agent is assigned to; backend enforces this.
- User: Creates property for self; do not pass `owner_id`.

Authorization header is required for all calls: `Authorization: Bearer <token>`.

### Data Pre-Fetch (populate form controls)

- Users list for owner selection (Admin/Agent only): `GET /api/v1/users/?page=1&limit=20&q=<search>`
- Amenities for multi-select: `GET /api/v1/amenities/`
- Optional: Agents listing (for contextual display), not required for creation.

### Form Sections and Fields

- Basic Info: `title` (required), `description`
- Classification: `property_type` (enum: apartment | house | builder_floor | room), `purpose` (enum: buy | rent | short_stay)
- Pricing: `base_price` (required), optional `price_per_sqft`, `monthly_rent`, `daily_rate`, `security_deposit`, `maintenance_charges`
- Location: `latitude`, `longitude`, `city`, `state`, `country` (default India), `pincode`, `locality`, `sub_locality`, `landmark`, `full_address`
- Details: `area_sqft`, `bedrooms`, `bathrooms`, `balconies`, `parking_spaces`, `floor_number`, `total_floors`, `age_of_property`, `max_occupancy`, `minimum_stay_days`
- Amenities & Features: `amenity_ids` (array of amenity IDs), `features` (array of strings), `tags` (array of strings)
- Owner Info (displayed, optionally editable): `owner_name`, `owner_contact`, `builder_name`
- Media: `main_image_url` (string URL). Gallery images: see Image Handling below.

Validation highlights (backend):
- Title length and sanitization enforced; description HTML sanitized.
- `base_price` must be >= 0.
- If both latitude and longitude provided, they must be valid coordinates; backend sets a PostGIS point automatically.
- `pincode` validated when provided.

### Location Selection UX

- Provide two capture modes:
  - Manual: Two inputs for `latitude` and `longitude`.
  - Map pick: Use a map component (Leaflet/Google Maps/Mapbox). On click or place search, set `latitude` and `longitude` in form state.
- Optional: Reverse geocode to suggest `city`, `locality`, and `full_address` (client-side only; backend does not reverse geocode).
- Submit the numeric `latitude` and `longitude`; backend persists a geospatial point for search/sorting.

### Image Handling (Supabase Storage)

Backend centralizes uploads to Supabase; the portal should upload files to the backend, not directly to Supabase.

- Endpoint: `POST /api/v1/upload/` (multipart form-data, field: `file`)
- Returns: `{ file_path, public_url, file_type, file_size, content_type, original_filename }`
- Allowed image types: `image/jpeg`, `image/jpg`, `image/png`, `image/webp`, `image/gif`

Recommended flow:
- Step 1: User selects images locally; for each file, call `POST /upload/` and collect returned `public_url`s.
- Step 2: Choose one image as the “Main Image” and set `main_image_url` in the property creation payload.
- Step 3: Submit the create-property request. Gallery images persistence is planned (see “Gallery images — planned API” below). For now, store only `main_image_url` server-side.

Notes:
- Current upload route stores files in a generic folder and returns a `public_url`. The bucket name is configured server-side.
- A specialized upload to `properties/{property_id}` exists at the service layer and will be exposed via a property-scoped API (see planned API below).

### Create Property — API Contract

- Endpoint: `POST /api/v1/properties/`
- Query: `owner_id` (int, optional; admin/agent only)
- Body (example):
```json
{
  "title": "Premium 3BHK Apartment in DLF Phase 1",
  "description": "Spacious 3BHK apartment with modern amenities and excellent location",
  "property_type": "apartment",
  "purpose": "rent",
  "base_price": 45000,
  "latitude": 28.4464,
  "longitude": 77.011711,
  "city": "Gurgaon",
  "state": "Haryana",
  "locality": "DLF Phase 1",
  "pincode": "122002",
  "area_sqft": 1400,
  "bedrooms": 3,
  "bathrooms": 2,
  "balconies": 2,
  "parking_spaces": 1,
  "floor_number": 8,
  "total_floors": 20,
  "age_of_property": 3,
  "max_occupancy": 5,
  "minimum_stay_days": 30,
  "amenity_ids": [1, 2, 3],
  "features": ["gym", "pool", "power_backup"],
  "tags": ["near_metro", "corner_unit"],
  "main_image_url": "https://<supabase-public-url>/uploads/uuid.jpg",
  "owner_name": "Property Owner",
  "owner_contact": "+911234567890",
  "builder_name": "DLF"
}
```

Backend behavior:
- Owner resolution: If `owner_id` is provided, backend enforces role and agent-user linkage; else owner is the current user.
- Geospatial field `location` is set from `latitude` and `longitude` when both present.
- The created property is returned as a full property object; `images` will be empty until gallery APIs are added; `amenities` are populated once amenity linking is implemented (see note below).

Important note about amenities: The request accepts `amenity_ids`. Display and filtering by amenities are supported in search, but amenity linking during creation/update is being finalized in the service layer. Keep sending `amenity_ids`; it will be used once the linking logic is enabled.

### End-to-End Creation Flow (UI sequence)

1) Load owners (Admin/Agent): `GET /users/` with search and pagination.
2) Load amenities: `GET /amenities/` to populate a multi-select.
3) User selects images; upload each via `POST /upload/`; collect `public_url`s.
4) Map pick or manual entry for `latitude` and `longitude` (optional but recommended).
5) Build property payload; set `main_image_url` using the chosen uploaded image URL; include selected `amenity_ids`.
6) Submit `POST /properties/?owner_id=<ownerId>` (omit `owner_id` for self-owned).
7) On success, navigate to property details page; surface the “Add Gallery Images” action once that API is available.

### RTK Query Snippets (Frontend)

Create an API slice or extend the existing base API.

```typescript
// propertiesApi.ts
import { api } from './api';

export const propertiesApi = api.injectEndpoints({
  endpoints: (build) => ({
    uploadFile: build.mutation<
      { public_url: string; file_path: string },
      FormData
    >({
      query: (form) => ({
        url: '/upload/',
        method: 'POST',
        body: form,
      }),
    }),
    createProperty: build.mutation<any, { payload: any; ownerId?: number }>({
      query: ({ payload, ownerId }) => ({
        url: ownerId ? `/properties/?owner_id=${ownerId}` : '/properties/',
        method: 'POST',
        body: payload,
      }),
      invalidatesTags: ['Property'],
    }),
  }),
});

export const { useUploadFileMutation, useCreatePropertyMutation } = propertiesApi;
```

Usage in component:

```typescript
const [uploadFile] = useUploadFileMutation();
const [createProperty, { isLoading }] = useCreatePropertyMutation();

async function handleCreate(formValues: any, files: File[], ownerId?: number) {
  // 1) Upload images
  const uploaded: string[] = [];
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    const res = await uploadFile(fd).unwrap();
    uploaded.push(res.public_url);
  }

  // 2) Choose main image
  const mainImageUrl = uploaded[0] || undefined;

  // 3) Build payload
  const payload = {
    ...formValues,
    latitude: formValues.latitude ? Number(formValues.latitude) : undefined,
    longitude: formValues.longitude ? Number(formValues.longitude) : undefined,
    amenity_ids: formValues.amenity_ids || undefined,
    main_image_url: mainImageUrl,
  };

  // 4) Create property
  const created = await createProperty({ payload, ownerId }).unwrap();
  return created;
}
```

### Gallery Images — Planned API (for reference)

To persist a property gallery and maintain ordering/main flag, the backend will expose property-scoped endpoints that use the existing storage service foldering (`properties/{property_id}`):

- `POST /api/v1/properties/{property_id}/images/` — multipart upload(s) using `files[]`; returns created rows with `image_url`, `display_order`, `is_main_image`.
- `PUT /api/v1/properties/{property_id}/images/{image_id}` — update caption/order/main flag.
- `DELETE /api/v1/properties/{property_id}/images/{image_id}` — delete image.

Until these endpoints land, store `main_image_url` only. Keep gallery `public_url`s in UI state for preview if needed.

### Error States & Edge Cases

- 400 on invalid image type; restrict file inputs to allowed content types.
- 403 if an agent attempts to create a property for a user they do not manage, or if a non-admin/non-agent passes `owner_id`.
- 404 if `owner_id` references a non-existent user.
- Missing `latitude`/`longitude` is allowed; property will be created but won’t benefit from geo search/sort until updated.
- Use optimistic UI and toasts; show server errors from the response `detail` field when present.

### QA Checklist (Portal)

- Owner selection honors RBAC and `owner_id` behavior.
- Amenities load and multi-select works; IDs are passed in payload.
- Map pick correctly updates lat/lng; manual entry validated as numbers.
- Upload returns `public_url`; main image is set in payload and shows in property card.
- Create call returns property and navigates to its details page.

### Amenities

#### GET `/amenities/`
- **Description**: List all active amenities for forms
- **Access**: Public
- **Response**:
  ```json
  [
    {
      "id": 1,
      "name": "Swimming Pool",
      "category": "leisure",
      "description": "Outdoor swimming pool",
      "icon": "pool",
      "is_active": true
    },
    {
      "id": 2,
      "name": "Gym",
      "category": "fitness",
      "description": "Fully equipped gym",
      "icon": "fitness_center",
      "is_active": true
    }
  ]
  ```

### Uploads

#### POST `/upload/`
- **Description**: Upload a file
- **Access**: Any authenticated user
- **Request**: Multipart form-data with `file` field
- **File Restrictions**:
  - Max size: 5MB
  - Allowed types: Images (jpg, png, gif), Documents (pdf)
- **Response**:
  ```json
  {
    "file_path": "uploads/2024/01/01/file_123.jpg",
    "public_url": "https://example.com/uploads/2024/01/01/file_123.jpg",
    "filename": "file_123.jpg",
    "content_type": "image/jpeg",
    "size": 1024000
  }
  ```

### Visits

#### POST `/visits/`
- **Description**: Schedule a property visit
- **Access**: Any authenticated user
- **Request Body**:
  ```json
  {
    "property_id": 123,
    "scheduled_date": "2024-12-01T10:00:00Z",
    "special_requirements": "Need parking space"
  }
  ```
- **Response**: Created visit object with assigned agent

#### GET `/visits/`
- **Description**: Get current user's visits
- **Access**: Any authenticated user
- **Response**:
  ```json
  {
    "visits": [...],
    "total": 5,
    "upcoming": 2,
    "completed": 3,
    "cancelled": 0
  }
  ```

#### GET `/visits/upcoming/`
- **Description**: Get upcoming visits for current user
- **Access**: Any authenticated user
- **Response**: Array of upcoming visits

#### GET `/visits/past/`
- **Description**: Get past visits for current user
- **Access**: Any authenticated user
- **Response**: Array of past visits

#### GET `/visits/{visit_id}`
- **Description**: Get visit details
- **Access**: Visit owner only
- **Response**: Complete visit object

#### PUT `/visits/{visit_id}`
- **Description**: Update visit details
- **Access**: Visit owner only
- **Request Body**: Visit update fields
- **Response**: Updated visit object

#### POST `/visits/{visit_id}/reschedule`
- **Description**: Reschedule a visit
- **Access**: Visit owner only
- **Request Body**:
  ```json
  {
    "new_date": "2024-12-02T10:00:00Z",
    "reason": "Schedule conflict"
  }
  ```
- **Response**: Updated visit object

#### POST `/visits/{visit_id}/cancel`
- **Description**: Cancel a visit
- **Access**: Visit owner only
- **Request Body**:
  ```json
  {
    "reason": "Changed plans"
  }
  ```
- **Response**: Updated visit object

#### GET `/visits/all/`
- **Description**: List all visits (admin/agent view)
- **Access**:
  - Admin: Can view all visits
  - Agent: Can view visits for assigned users/properties
- **Query Parameters**:
  - `page`: int (default: 1)
  - `limit`: int (default: 20)
  - `status`: str (optional) - Filter by status
  - `agent_id`: int (optional, admin only) - Filter by agent
  - `property_id`: int (optional) - Filter by property
  - `user_id`: int (optional) - Filter by user
- **Response**: Paginated visits list

#### POST `/visits/{visit_id}/complete/`
- **Description**: Mark visit as completed
- **Access**: Admin or assigned agent
- **Request Body** (optional):
  ```json
  {
    "notes": "Client was interested in the property",
    "feedback": "Good property, matches client requirements"
  }
  ```
- **Response**: Updated visit object

### Bookings

#### POST `/bookings/`
- **Description**: Create a new booking
- **Access**: Any authenticated user
- **Request Body**:
  ```json
  {
    "property_id": 123,
    "check_in_date": "2024-12-01T14:00:00Z",
    "check_out_date": "2024-12-03T12:00:00Z",
    "guests": 2,
    "primary_guest_name": "John Doe",
    "primary_guest_phone": "+1234567890",
    "primary_guest_email": "john@example.com",
    "special_requests": "Early check-in if possible",
    "guest_details": {}
  }
  ```
- **Response**: Created booking object

#### GET `/bookings/`
- **Description**: Get current user's bookings
- **Access**: Any authenticated user
- **Response**: `BookingList` object with summary counts

#### GET `/bookings/upcoming/`
- **Description**: Get upcoming bookings for current user
- **Access**: Any authenticated user
- **Response**: Array of upcoming bookings

#### GET `/bookings/past/`
- **Description**: Get past bookings for current user
- **Access**: Any authenticated user
- **Response**: Array of past bookings

#### POST `/bookings/check-availability/`
- **Description**: Check booking availability
- **Access**: Public
- **Request Body**:
  ```json
  {
    "property_id": 123,
    "check_in_date": "2024-12-01T14:00:00Z",
    "check_out_date": "2024-12-03T12:00:00Z"
  }
  ```
- **Response**: Availability information

#### POST `/bookings/calculate-pricing/`
- **Description**: Calculate booking pricing
- **Access**: Public
- **Request Body**: Same as check-availability
- **Response**:
  ```json
  {
    "base_price": 25000,
    "total_nights": 2,
    "subtotal": 50000,
    "taxes": 9000,
    "service_fee": 1000,
    "total_amount": 60000,
    "currency": "INR",
    "breakdown": [...]
  }
  ```

#### GET `/bookings/{booking_id}`
- **Description**: Get booking details
- **Access**: Booking owner or authorized agent
- **Response**: Complete booking object

#### PUT `/bookings/{booking_id}`
- **Description**: Update booking details
- **Access**: Booking owner only
- **Request Body**: Booking update fields
- **Response**: Updated booking object

#### POST `/bookings/cancel/`
- **Description**: Cancel a booking
- **Access**: Booking owner only
- **Request Body**:
  ```json
  {
    "reason": "Changed plans"
  }
  ```
- **Response**: `{"message": "Booking cancelled successfully"}`

#### POST `/bookings/payment/`
- **Description**: Process booking payment
- **Access**: Booking owner or authorized agent
- **Request Body**:
  ```json
  {
    "payment_method": "card",
    "transaction_id": "txn_123",
    "amount": 60000
  }
  ```
- **Response**: `{"message": "Payment processed successfully"}`

#### POST `/bookings/review/`
- **Description**: Add booking review
- **Access**: Booking owner or authorized agent
- **Request Body**:
  ```json
  {
    "rating": 5,
    "review_text": "Excellent property and host",
    "aspects": {
      "cleanliness": 5,
      "location": 5,
      "value": 4,
      "communication": 5
    }
  }
  ```
- **Response**: `{"message": "Review added successfully"}`

#### GET `/bookings/all/`
- **Description**: List all bookings (admin/agent view)
- **Access**:
  - Admin: Can view all bookings
  - Agent: Can view bookings for assigned users/properties
- **Query Parameters**:
  - `page`: int (default: 1)
  - `limit`: int (default: 20)
  - `status`: str (optional) - Filter by status
  - `agent_id`: int (optional, admin only) - Filter by agent
  - `property_id`: int (optional) - Filter by property
  - `user_id`: int (optional) - Filter by user
- **Response**: Paginated bookings list

### Core System

#### Bug Reports

##### POST `/bugs/`
- **Description**: Create a new bug report
- **Access**: Any authenticated user
- **Request Body**:
  ```json
  {
    "source": "mobile",
    "bug_type": "ui_bug",
    "severity": "medium",
    "title": "Login button not working",
    "description": "When clicking login button, nothing happens",
    "steps_to_reproduce": "1. Open app 2. Click login 3. Nothing happens",
    "expected_behavior": "Should navigate to login screen",
    "actual_behavior": "Button is unresponsive",
    "device_info": {
      "os": "iOS",
      "version": "17.0",
      "model": "iPhone 14"
    },
    "app_version": "1.2.3",
    "tags": ["login", "ui", "button"]
  }
  ```
- **Response**: Created bug report object

##### POST `/bugs/with-media/`
- **Description**: Create bug report with media attachments
- **Access**: Any authenticated user
- **Request**: Multipart form-data with fields and file uploads
- **Response**: Created bug report with media URLs

##### GET `/bugs/`
- **Description**: List bug reports with filtering
- **Access**:
  - Admin: Can view all bug reports
  - Agent: Can view bug reports from assigned users
  - User: Can view own bug reports
- **Query Parameters**:
  - `status`: str (optional) - Filter by status (open, in_progress, resolved, closed)
  - `bug_type`: str (optional) - Filter by bug type
  - `limit`: int (default: 20, min: 1, max: 100) - Number of results
  - `offset`: int (default: 0, min: 0) - Pagination offset
- **Response**: List of bug reports

##### GET `/bugs/{bug_id}`
- **Description**: Get specific bug report details
- **Access**: Bug report owner or admin
- **Response**: Complete bug report object

##### PUT `/bugs/{bug_id}`
- **Description**: Update bug report
- **Access**:
  - Admin: Can update any field
  - Agent: Can update status for assigned users' bugs
  - User: Can update limited fields of own bugs
- **Request Body**: Bug report update fields
- **Response**: Updated bug report

#### Pages Management

##### POST `/pages/`
- **Description**: Create a new page
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "unique_name": "privacy-policy",
    "title": "Privacy Policy",
    "content": "<h1>Privacy Policy</h1><p>Our privacy policy content...</p>",
    "format": "html",
    "custom_config": {
      "show_footer": true,
      "enable_sharing": false,
      "meta_description": "Read our privacy policy"
    },
    "is_active": true,
    "is_draft": false
  }
  ```
- **Response**: Created page object

##### GET `/pages/`
- **Description**: List all pages
- **Access**: Admin only
- **Query Parameters**:
  - `is_active`: bool (optional)
  - `is_draft`: bool (optional)
  - `limit`: int (default: 20, min: 1, max: 100) - Number of results
  - `offset`: int (default: 0, min: 0) - Pagination offset
- **Response**: List of pages

##### GET `/pages/{unique_name}`
- **Description**: Get page by unique name
- **Access**: Admin only
- **Response**: Page object

##### GET `/pages/{unique_name}/public`
- **Description**: Get page content for public access
- **Access**: Public (no authentication required)
- **Response**: Public page object (without sensitive fields)

##### PUT `/pages/{unique_name}`
- **Description**: Update page content
- **Access**: Admin only
- **Request Body**: Page update fields
- **Response**: Updated page object

##### DELETE `/pages/{unique_name}`
- **Description**: Delete (soft delete) a page
- **Access**: Admin only
- **Response**: Success message

#### App Updates

##### POST `/updates/`
- **Description**: Create a new app update entry
- **Access**: Admin only
- **Request Body**:
  ```json
  {
    "platform": "ios",
    "version": "1.2.4",
    "build_number": 124,
    "release_notes": "Bug fixes and performance improvements",
    "download_url": "https://apps.apple.com/app/360ghar/id123456789",
    "is_mandatory": false,
    "is_active": true,
    "min_supported_version": "1.0.0"
  }
  ```
- **Response**: Created app update object

##### POST `/updates/check`
- **Description**: Check if there's an available update
- **Access**: Public (no authentication required)
- **Request Body**:
  ```json
  {
    "platform": "ios",
    "current_version": "1.2.3",
    "build_number": 123
  }
  ```
- **Response**:
  ```json
  {
    "update_available": true,
    "is_mandatory": false,
    "latest_version": "1.2.4",
    "download_url": "https://apps.apple.com/app/360ghar/id123456789",
    "release_notes": "Bug fixes and performance improvements",
    "min_supported_version": "1.0.0"
  }
  ```

##### GET `/updates/`
- **Description**: List all app updates
- **Access**: Admin only
- **Query Parameters**:
  - `platform`: str (optional) - ios, android, web
  - `is_active`: bool (optional)
  - `limit`: int (default: 10, min: 1, max: 100) - Number of results
  - `offset`: int (default: 0, min: 0) - Pagination offset
- **Response**: List of app updates

##### PUT `/updates/{update_id}`
- **Description**: Update app update entry
- **Access**: Admin only
- **Request Body**: App update fields to update
- **Response**: Updated app update object

#### System Health

##### GET `/health`
- **Description**: System health check
- **Access**: Public (no authentication required)
- **Response**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "service": "360ghar-core"
  }
  ```

##### GET `/config`
- **Description**: Get application configuration info (non-sensitive settings)
- **Access**: Public (no authentication required)
- **Response**: Configuration details about the application

## RTK Query Setup

```typescript
// api.ts
export const api = createApi({
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/v1',
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: () => ({}),
  tagTypes: ['User', 'Agent', 'Property', 'Visit', 'Booking', 'BugReport', 'Page', 'AppUpdate', 'Amenity'],
});
```

### RTK Query API Services

#### usersApi
```typescript
usersApi.injectEndpoints({
  endpoints: (builder) => ({
    // List users (admin/agent)
    getUsers: builder.query<PaginatedResponse<User>, UsersQuery>({
      query: (params) => ({
        url: '/users/',
        params: { page: 1, limit: 20, ...params }
      }),
      providesTags: ['User']
    }),

    // Get user by ID
    getUser: builder.query<User, number>({
      query: (id) => `/users/${id}/`,
      providesTags: ['User']
    }),

    // Update user
    updateUser: builder.mutation<User, { id: number; data: Partial<UserUpdate> }>({
      query: ({ id, data }) => ({
        url: `/users/${id}/`,
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['User']
    }),

    // Assign agent to user
    assignAgent: builder.mutation<void, { userId: number; agentId: number }>({
      query: ({ userId, agentId }) => ({
        url: `/users/${userId}/assign-agent/`,
        method: 'POST',
        body: { agent_id: agentId }
      }),
      invalidatesTags: ['User', 'Agent']
    }),

    // Get user profile
    getProfile: builder.query<User, void>({
      query: () => '/users/profile/',
      providesTags: ['User']
    }),

    // Update profile
    updateProfile: builder.mutation<User, Partial<UserUpdate>>({
      query: (data) => ({
        url: '/users/profile/',
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['User']
    })
  })
});
```

#### agentsApi
```typescript
agentsApi.injectEndpoints({
  endpoints: (builder) => ({
    // List agents (admin)
    getAgents: builder.query<Agent[], { includeInactive?: boolean }>({
      query: (params) => ({
        url: '/agents/',
        params
      }),
      providesTags: ['Agent']
    }),

    // Create agent (admin)
    createAgent: builder.mutation<Agent, AgentCreate>({
      query: (data) => ({
        url: '/agents/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Agent']
    }),

    // Get agent profile (current user)
    getAgentProfile: builder.query<Agent, void>({
      query: () => '/agents/me/',
      providesTags: ['Agent']
    }),

    // Get assigned agent
    getAssignedAgent: builder.query<Agent | null, void>({
      query: () => '/agents/assigned/',
      providesTags: ['Agent']
    }),

    // Get available agents
    getAvailableAgents: builder.query<Agent[], { specialization?: string; agentType?: string }>({
      query: (params) => ({
        url: '/agents/available/',
        params
      }),
      providesTags: ['Agent']
    }),

    // Get system workload (admin)
    getSystemWorkload: builder.query<AgentWorkload[], void>({
      query: () => '/agents/system/workload/',
      providesTags: ['Agent']
    }),

    // Toggle agent availability (admin)
    toggleAgentAvailability: builder.mutation<void, { agentId: number; isAvailable: boolean }>({
      query: ({ agentId, isAvailable }) => ({
        url: `/agents/${agentId}/availability/`,
        method: 'PATCH',
        body: { is_available: isAvailable }
      }),
      invalidatesTags: ['Agent']
    })
  })
});
```

#### propertiesApi
```typescript
propertiesApi.injectEndpoints({
  endpoints: (builder) => ({
    // Search properties
    searchProperties: builder.query<UnifiedPropertyResponse, PropertySearchParams>({
      query: (params) => ({
        url: '/properties/',
        params: { page: 1, limit: 20, ...params }
      }),
      providesTags: ['Property']
    }),

    // Get property details
    getProperty: builder.query<Property, number>({
      query: (id) => `/properties/${id}`,
      providesTags: ['Property']
    }),

    // Create property
    createProperty: builder.mutation<Property, { data: PropertyCreate; ownerId?: number }>({
      query: ({ data, ownerId }) => ({
        url: '/properties/',
        method: 'POST',
        params: ownerId ? { owner_id: ownerId } : undefined,
        body: data
      }),
      invalidatesTags: ['Property']
    }),

    // Update property
    updateProperty: builder.mutation<Property, { id: number; data: Partial<PropertyUpdate> }>({
      query: ({ id, data }) => ({
        url: `/properties/${id}`,
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['Property']
    }),

    // Delete property
    deleteProperty: builder.mutation<void, number>({
      query: (id) => ({
        url: `/properties/${id}/`,
        method: 'DELETE'
      }),
      invalidatesTags: ['Property']
    }),

    // Get recommendations
    getRecommendations: builder.query<Property[], { limit?: number }>({
      query: (params) => ({
        url: '/properties/recommendations/',
        params: { limit: 10, ...params }
      }),
      providesTags: ['Property']
    })
  })
});
```

#### visitsApi
```typescript
visitsApi.injectEndpoints({
  endpoints: (builder) => ({
    // Schedule visit
    scheduleVisit: builder.mutation<Visit, VisitCreate>({
      query: (data) => ({
        url: '/visits/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Visit', 'Property']
    }),

    // Get user visits
    getUserVisits: builder.query<VisitList, void>({
      query: () => '/visits/',
      providesTags: ['Visit']
    }),

    // Get all visits (admin/agent)
    getAllVisits: builder.query<PaginatedResponse<Visit>, VisitsQuery>({
      query: (params) => ({
        url: '/visits/all/',
        params: { page: 1, limit: 20, ...params }
      }),
      providesTags: ['Visit']
    }),

    // Complete visit
    completeVisit: builder.mutation<Visit, { visitId: number; notes?: string; feedback?: string }>({
      query: ({ visitId, ...data }) => ({
        url: `/visits/${visitId}/complete/`,
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Visit']
    }),

    // Reschedule visit
    rescheduleVisit: builder.mutation<Visit, { visitId: number; newDate: string; reason: string }>({
      query: ({ visitId, ...data }) => ({
        url: `/visits/${visitId}/reschedule`,
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Visit']
    })
  })
});
```

#### bookingsApi
```typescript
bookingsApi.injectEndpoints({
  endpoints: (builder) => ({
    // Create booking
    createBooking: builder.mutation<Booking, BookingCreate>({
      query: (data) => ({
        url: '/bookings/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Booking', 'Property']
    }),

    // Get user bookings
    getUserBookings: builder.query<BookingList, void>({
      query: () => '/bookings/',
      providesTags: ['Booking']
    }),

    // Get all bookings (admin/agent)
    getAllBookings: builder.query<PaginatedResponse<Booking>, BookingsQuery>({
      query: (params) => ({
        url: '/bookings/all/',
        params: { page: 1, limit: 20, ...params }
      }),
      providesTags: ['Booking']
    }),

    // Check availability
    checkAvailability: builder.query<AvailabilityInfo, BookingAvailability>({
      query: (data) => ({
        url: '/bookings/check-availability/',
        method: 'POST',
        body: data
      })
    }),

    // Calculate pricing
    calculatePricing: builder.query<BookingPricing, BookingAvailability>({
      query: (data) => ({
        url: '/bookings/calculate-pricing/',
        method: 'POST',
        body: data
      })
    }),

    // Process payment
    processPayment: builder.mutation<void, { bookingId: number; paymentData: BookingPayment }>({
      query: ({ bookingId, ...data }) => ({
        url: '/bookings/payment/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Booking']
    }),

    // Add review
    addReview: builder.mutation<void, { bookingId: number; reviewData: BookingReview }>({
      query: ({ bookingId, ...data }) => ({
        url: '/bookings/review/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Booking', 'Property']
    })
  })
});
```

#### amenitiesApi
```typescript
amenitiesApi.injectEndpoints({
  endpoints: (builder) => ({
    // Get all amenities
    getAmenities: builder.query<Amenity[], void>({
      query: () => '/amenities/'
    })
  })
});
```

#### uploadApi
```typescript
uploadApi.injectEndpoints({
  endpoints: (builder) => ({
    // Upload file
    uploadFile: builder.mutation<UploadResponse, File>({
      query: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return {
          url: '/upload/',
          method: 'POST',
          body: formData
        };
      }
    })
  })
});
```

#### coreApi
```typescript
coreApi.injectEndpoints({
  endpoints: (builder) => ({
    // Bug Reports
    createBugReport: builder.mutation<BugReportResponse, BugReportCreate>({
      query: (data) => ({
        url: '/bugs/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['BugReport']
    }),

    createBugReportWithMedia: builder.mutation<BugReportResponse, FormData>({
      query: (formData) => ({
        url: '/bugs/with-media/',
        method: 'POST',
        body: formData,
        formData: true
      }),
      invalidatesTags: ['BugReport']
    }),

    getBugReports: builder.query<BugReportResponse[], BugReportsQuery>({
      query: (params) => ({
        url: '/bugs/',
        params: { limit: 20, offset: 0, ...params }
      }),
      providesTags: ['BugReport']
    }),

    getBugReport: builder.query<BugReportResponse, number>({
      query: (id) => `/bugs/${id}`,
      providesTags: ['BugReport']
    }),

    updateBugReport: builder.mutation<BugReportResponse, { id: number; data: BugReportUpdate }>({
      query: ({ id, data }) => ({
        url: `/bugs/${id}`,
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['BugReport']
    }),

    // Pages
    createPage: builder.mutation<PageResponse, PageCreate>({
      query: (data) => ({
        url: '/pages/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['Page']
    }),

    getPages: builder.query<PageResponse[], PagesQuery>({
      query: (params) => ({
        url: '/pages/',
        params: { limit: 20, offset: 0, ...params }
      }),
      providesTags: ['Page']
    }),

    getPage: builder.query<PageResponse, string>({
      query: (uniqueName) => `/pages/${uniqueName}`,
      providesTags: ['Page']
    }),

    getPagePublic: builder.query<PagePublicResponse, string>({
      query: (uniqueName) => `/pages/${uniqueName}/public`
    }),

    updatePage: builder.mutation<PageResponse, { uniqueName: string; data: PageUpdate }>({
      query: ({ uniqueName, data }) => ({
        url: `/pages/${uniqueName}`,
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['Page']
    }),

    deletePage: builder.mutation<void, string>({
      query: (uniqueName) => ({
        url: `/pages/${uniqueName}`,
        method: 'DELETE'
      }),
      invalidatesTags: ['Page']
    }),

    // App Updates
    createAppUpdate: builder.mutation<AppUpdateResponse, AppUpdateCreate>({
      query: (data) => ({
        url: '/updates/',
        method: 'POST',
        body: data
      }),
      invalidatesTags: ['AppUpdate']
    }),

    checkForUpdates: builder.query<AppUpdateCheckResponse, AppUpdateCheckRequest>({
      query: (data) => ({
        url: '/updates/check',
        method: 'POST',
        body: data
      })
    }),

    getAppUpdates: builder.query<AppUpdateResponse[], AppUpdatesQuery>({
      query: (params) => ({
        url: '/updates/',
        params: { limit: 10, offset: 0, ...params }
      }),
      providesTags: ['AppUpdate']
    }),

    updateAppUpdate: builder.mutation<AppUpdateResponse, { id: number; data: AppUpdateUpdate }>({
      query: ({ id, data }) => ({
        url: `/updates/${id}`,
        method: 'PUT',
        body: data
      }),
      invalidatesTags: ['AppUpdate']
    }),

    // Health Check
    healthCheck: builder.query<HealthResponse, void>({
      query: () => '/health'
    })
  })
});
```

## Schema Types

### Common Types
```typescript
// Most list endpoints return arrays directly or specialized response types
// Some endpoints use PaginatedResponse with items, total, page, limit, etc.

interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: 'user' | 'agent' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  agent_id?: number;
  agent?: Agent;
  supabase_user_id: string;
  created_at: string;
  updated_at: string;
  preferences?: UserPreferences;
  date_of_birth?: string;
  profile_image_url?: string;
  current_latitude?: number;
  current_longitude?: number;
  preferred_locations?: string[];
  notification_settings?: Record<string, boolean>;
  privacy_settings?: Record<string, any>;
}

interface Agent {
  id: number;
  user_id: number;
  name: string;
  description?: string;
  avatar_url?: string;
  languages: string[];
  agent_type: 'general' | 'specialist' | 'senior';
  experience_level: 'beginner' | 'intermediate' | 'expert';
  working_hours: Record<string, any>;
  is_active: boolean;
  is_available: boolean;
  total_users_assigned: number;
  user_satisfaction_rating: number;
  created_at: string;
  updated_at: string;
}

interface AgentWithStats extends Agent {
  total_conversations: number;
  total_interactions: number;
  avg_response_time_minutes: number;
  satisfaction_rate: number;
  efficiency_score: number;
}

interface AgentWorkload {
  agent_id: number;
  agent_name: string;
  active_clients: number;
  pending_visits: number;
  active_bookings: number;
  utilization_rate: number;
  max_capacity: number;
}
```

## Error Handling Patterns

```typescript
// API response wrapper
interface ApiResponse<T> {
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

// RTK Query base query with error handling
const baseQuery = fetchBaseQuery({
  baseUrl: '/api/v1',
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.token;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return headers;
  },
});

// Custom base query with global error handling
const baseQueryWithErrorHandling: BaseQueryFn<string | FetchArgs, unknown, ApiError> = async (
  args,
  api,
  extraOptions
) => {
  const result = await baseQuery(args, api, extraOptions);

  if (result.error) {
    // Handle specific error cases
    if (result.error.status === 401) {
      // Redirect to login
      window.location.href = '/login';
    }

    // Transform error format
    return {
      error: {
        status: result.error.status,
        data: result.error.data
      }
    };
  }

  return result;
};
```

## Notes & Best Practices

### Authentication & Authorization
- **Server-side RBAC**: Always enforce permissions on the server
- **Client-side gating**: Hide/disable UI elements based on user role
- **Token refresh**: Handle Supabase token refresh automatically
- **Error handling**: Show appropriate messages for auth errors

### Data Fetching
- **Pagination**: Use server pagination for large datasets
- **Caching**: Leverage RTK Query's built-in caching
- **Invalidation**: Invalidate tags when data changes
- **Optimistic updates**: Use for better UX on non-critical operations

### Forms & Validation
- **Zod schemas**: Reuse backend schemas for validation
- **Type safety**: Use TypeScript for all API interactions
- **Error display**: Show field-specific validation errors
- **Debouncing**: Debounce search inputs to reduce API calls

### UI/UX Patterns
- **Loading states**: Show loading indicators for async operations
- **Error toasts**: Display error messages from API responses
- **Success feedback**: Show confirmation for successful actions
- **Empty states**: Handle empty lists gracefully

### Performance
- **Parallel requests**: Batch multiple requests when possible
- **Prefetching**: Prefetch data for likely user actions
- **Image optimization**: Use lazy loading and responsive images
- **Code splitting**: Split code by route/feature

This comprehensive documentation provides all the necessary information to build a fully functional admin and agent portal for the 360Ghar platform.
