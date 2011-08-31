/** 
 Copyright (c) 2011 Bogdano Arendartchuk <bogdano@mandriva.com.br>

 Written by Bogdano Arendartchuk <bogdano@mandriva.com.br>

 This file is part of Jurt Build Bot.

 Jurt Build Bot is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published
 by the Free Software Foundation; either version 2 of the License, or (at
 your option) any later version.

 Jurt Build Bot is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Jurt Build Bot; if not, write to the Free Software
 Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/
/** Small wrapper around jurt-root-command, as an alternative to sudo */
#include <unistd.h>
#include <sys/types.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define DEBUG_ENV	"JURT_SUID_DEBUG"
#ifndef JURT_ROOT_COMMAND
#define JURT_ROOT_COMMAND /usr/sbin/jurt-root-command
#endif
#define XSTR(s) STR(s)
#define STR(s) #s
#define _JURT_ROOT_COMMAND XSTR(JURT_ROOT_COMMAND)

int main(int argc, char *argv[])
{
	int i;
	char **newargs;

	if (getenv(DEBUG_ENV)) {
		printf("real uid: %d\n", getuid());
		printf("effective uid: %d\n", geteuid());
		printf("jurt-root-command: %s\n", _JURT_ROOT_COMMAND);
	}

	newargs = (char**) malloc(argc * sizeof(char*));
	if (!newargs)
		goto error;
	memset(newargs, 0, argc * sizeof(char*));

	newargs[0] = (char*) malloc(sizeof(_JURT_ROOT_COMMAND) + 0);
	if (!newargs[0])
		goto error;
	strcpy(newargs[0], _JURT_ROOT_COMMAND);

	for (i = 1; i < argc - 1; i++) {
		newargs[i] = (char*) malloc(strlen(argv[i+1]) + 1);
		if (!newargs[i])
			goto error;
		strcpy(newargs[i], argv[i+1]);
	}

	if (getenv(DEBUG_ENV))
		for (i = 0; i < argc - 1; i++)
			printf("callarg[%d]: %s\n", i, newargs[i]);

	if (setuid(0)) {
		perror("setuid");
		goto error;
	}

	return execv(newargs[0], newargs);
error:
	return 127;
}
