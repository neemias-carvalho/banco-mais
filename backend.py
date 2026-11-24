# Fachada de compatibilidade para app.py e views/
from services.connection import (
    get_db,
    hash_password,
    verify_password,
    init_db,
)
from services.auth_service import (
    create_session_token,
    validate_session_token,
    delete_session_token,
    login_user,
    change_password,
)
from services.school_service import (
    add_school,
    get_schools,
    get_all_schools_details,
    add_class,
    get_classes_by_school,
    get_school_and_class_names,
    get_students_school_map,
    register_teacher,
    register_student,
    get_all_students,
    get_all_teachers,
    update_user_school_and_class,
    get_all_student_usernames,
    get_student_usernames_by_class,
    get_students_by_class,
    get_students_by_school,
    get_other_users,
    get_balance,
)
from services.finance_service import (
    get_pending_outgoing_amount,
    request_deposit,
    request_withdraw,
    request_transfer,
    get_pending_operations,
    get_reviewed_operations,
    get_user_operation_requests,
    approve_operation,
    reject_operation,
    deposit_b_plus,
    transfer_b_plus,
    withdraw_b_plus,
    get_history,
)
