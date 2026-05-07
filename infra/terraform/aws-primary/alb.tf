resource "aws_lb" "this" {
  name               = "${local.name}-alb"
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]

  drop_invalid_header_fields = true
  idle_timeout               = 60
}

resource "aws_lb_target_group" "this" {
  name        = "${local.name}-tg"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/health/ready"
    matcher             = "200"
    interval            = 10
    timeout             = 3
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  deregistration_delay = 20
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}
