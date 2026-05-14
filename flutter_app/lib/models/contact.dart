class Contact {
  final String id;
  final String name;
  final String email;
  final String? phone;
  final String? company;

  const Contact({
    required this.id,
    required this.name,
    required this.email,
    this.phone,
    this.company,
  });

  factory Contact.fromJson(Map<String, dynamic> json) {
    return Contact(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      phone: json['phone']?.toString(),
      company: json['company']?.toString(),
    );
  }
}
