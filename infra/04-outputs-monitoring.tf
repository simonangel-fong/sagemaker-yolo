# # outputs-monitoring.tf

output "monitoring_dashboard_url" {
  description = "CloudWatch dashboard for the endpoint, predict lambda, and distribution."
  value       = var.enable_deploy ? "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards/dashboard/${aws_cloudwatch_dashboard.main[0].dashboard_name}" : null
}
