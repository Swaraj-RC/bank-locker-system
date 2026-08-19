export type UserRole = "CUSTOMER" | "BANK_OPERATOR" | "BRANCH_MANAGER" | "SUPER_ADMIN";

export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  role: UserRole;
  branch_id: string | null;
  status: string;
}

export type LockerStatus =
  | "AVAILABLE"
  | "OCCUPIED"
  | "VERIFICATION_PENDING"
  | "ACCESS_ACTIVE"
  | "MAINTENANCE"
  | "RESTRICTED";

export interface Locker {
  id: string;
  branch_id: string;
  locker_number: string;
  locker_size: string;
  status: LockerStatus;
  customer_id: string | null;
  last_operation_at: string | null;
}

export type RequestStatus =
  | "SUBMITTED"
  | "VERIFICATION_PENDING"
  | "TOKEN_A_VERIFIED"
  | "TOKEN_B_VERIFIED"
  | "APPROVAL_PENDING"
  | "APPROVED"
  | "ACCESS_ACTIVE"
  | "COMPLETED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED"
  | "MANUAL_REVIEW"   // face-verify: low confidence / liveness fail — needs human review
  | "BLOCKED";        // face-verify: terminal — attempt limit exhausted

export interface FaceVerification {
  id: string;
  request_id: string;
  actor_id: string;
  actor_role: string;
  face_match: boolean;
  confidence: number;
  liveness_passed: boolean;
  spoof_probability: number;
  attempt_number: number;
  created_at: string;
}

export interface LockerRequest {
  id: string;
  locker_id: string;
  customer_id: string;
  request_type: string;
  status: RequestStatus;
  requested_at: string;
  scheduled_at: string | null;
  approved_by: string | null;
  completed_at: string | null;
  rejection_reason: string | null;
  correlation_id: string;
  locker_number?: string;
  customer_name?: string;
}


export interface AuditEvent {
  id: string;
  actor_id: string | null;
  actor_role: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  previous_state: string | null;
  new_state: string | null;
  event_metadata: Record<string, unknown> | null;
  correlation_id: string | null;
  created_at: string;
}

export interface Branch {
  id: string;
  branch_code: string;
  name: string;
  address: string;
  city: string;
  state: string;
  status: string;
}

export interface DashboardKpis {
  total_lockers: number;
  occupied: number;
  available: number;
  active_requests: number;
  access_today: number;
  pending_verifications: number;
}
