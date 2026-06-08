export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface VerifyTokenResponse {
  valid: boolean;
  user: UserProfile | null;
}
