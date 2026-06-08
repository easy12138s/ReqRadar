export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
}
