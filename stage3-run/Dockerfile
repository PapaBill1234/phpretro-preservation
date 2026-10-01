FROM php:5.6-apache
RUN docker-php-ext-install mysql mysqli && a2enmod rewrite
COPY . /var/www/html/
RUN chown -R www-data:www-data /var/www/html
